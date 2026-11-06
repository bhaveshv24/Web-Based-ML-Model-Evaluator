// TSMP-21 browser system tests for the /results dashboard (ST-AUTH-01 sign-in/out part,
// ST-REP-01, ST-REP-02, ST-REP-03), driven through a real browser.
//
//   cd scripts/validation/browser && npm install
//   BASE_URL=http://localhost:8000 EMAIL=... PASSWORD=... node results_dashboard.mjs
//
// BROWSER selects the engine: "chrome" (default, the installed Google Chrome), "msedge" (the
// installed Microsoft Edge) or "firefox" (Playwright's Firefox build, installed with
// `npx playwright-core install firefox`). Chrome writes to docs/evidence/tsmp-21/ as before;
// any other browser writes to docs/evidence/tsmp-21/browser-<BROWSER>/ so the Chrome evidence
// is never overwritten.
//
// The account must own at least three SUCCEEDED classification evaluations on one dataset
// and one SUCCEEDED regression evaluation. Every check records its actual observation and PASS/FAIL.
import {mkdirSync, readFileSync, writeFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium, firefox} from "playwright-core";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../..");
const engine = process.env.BROWSER ?? "chrome";
const launchers = {
  chrome: () => chromium.launch({channel: "chrome", headless: true}),
  msedge: () => chromium.launch({channel: "msedge", headless: true}),
  firefox: () => firefox.launch({headless: true}),
};
const names = {chrome: "Google Chrome", msedge: "Microsoft Edge", firefox: "Firefox (Playwright build)"};
if (!launchers[engine]) throw new Error(`BROWSER must be one of ${Object.keys(launchers)}`);
const evidence = engine === "chrome" ? join(root, "docs/evidence/tsmp-21")
  : join(root, "docs/evidence/tsmp-21", `browser-${engine}`);
const shots = join(evidence, "screenshots");
mkdirSync(shots, {recursive: true});
const base = process.env.BASE_URL ?? "http://localhost:8000";
const results = [];
let shot = 0;

function record(id, requirement, description, expected, ok, actual, screenshot) {
  results.push({id, requirement, description, expected, actual, status: ok ? "PASS" : "FAIL",
    evidence: screenshot ?? null});
  console.log(`${ok ? "PASS" : "FAIL"} ${id}: ${actual}`);
}

async function capture(page, name) {
  shot += 1;
  const file = `${String(shot).padStart(2, "0")}-${name}.png`;
  await page.screenshot({path: join(shots, file), fullPage: true});
  return `screenshots/${file}`;
}

const browser = await launchers[engine]();
const context = await browser.newContext({viewport: {width: 1280, height: 720},
  acceptDownloads: true});
const page = await context.newPage();
const consoleErrors = [];
const failedResources = [];
page.on("console", (message) => message.type() === "error" && consoleErrors.push(message.text()));
page.on("response", (response) => response.status() >= 400 &&
  failedResources.push(`${response.status()} ${new URL(response.url()).pathname}`));
const version = browser.version();

try {
  // ------------------------------------------------------------------ sign in, history
  await page.goto(`${base}/results`);
  const loginShot = await capture(page, "sign-in");
  await page.fill("input[name=email]", process.env.EMAIL);
  await page.fill("input[name=password]", process.env.PASSWORD);
  await page.click("#login button");
  await page.waitForSelector("#history:not([hidden]) #runs tr td");
  const runRows = await page.locator("#runs tbody tr").count();
  const historyShot = await capture(page, "history");
  record("ST-AUTH-01(UI sign-in)", "FR-002, UI-01", "Sign in on /results",
    "History of completed runs shown after sign-in", runRows >= 4,
    `signed in; ${runRows} completed runs listed; login form hidden=` +
    `${await page.locator("#login").isHidden()}`, `${loginShot}, ${historyShot}`);

  const rows = page.locator("#runs tbody tr");
  const tasks = await rows.locator("td:nth-child(3)").allTextContents();
  const classification = tasks.map((t, i) => [t, i]).filter(([t]) => t === "classification");
  const regression = tasks.findIndex((t) => t === "regression");

  // ------------------------------------------------------------- ST-REP-01 classification
  await rows.nth(classification[0][1]).locator("button").click();
  await page.waitForSelector("#result:not([hidden]) #content .metric");
  const cards = await page.locator("#content .metric").allTextContents();
  const matrixRows = await page.locator("#content table").first().locator("tbody tr").count();
  const rocBefore = await page.locator("#content figure h3").first().textContent();
  const options = await page.locator("#content select option").allTextContents();
  await page.selectOption("#content select", options.at(-1));
  const rocAfter = await page.locator("#content figure h3").first().textContent();
  const curve = await page.locator("#content figure polyline.curve").count();
  const classShot = await capture(page, "classification-dashboard");
  record("ST-REP-01", "FR-022, UI-05", "Open a classification dashboard",
    "Metric cards, confusion matrix and ROC curve render",
    cards.some((c) => c.startsWith("Accuracy")) && matrixRows === 3 && curve === 1 &&
      options.length === 3,
    `${cards.length} metric cards (${cards.slice(0, 3).join("; ")}...); confusion matrix ` +
    `${matrixRows}x${matrixRows}; ROC classes [${options.join(", ")}]; switched ROC class: ` +
    `"${rocBefore}" -> "${rocAfter}"; download buttons=` +
    `${await page.locator("#downloads button").count()}`, classShot);

  // ----------------------------------------------------------------- ST-REP-02 regression
  await rows.nth(regression).locator("button").click();
  await page.waitForSelector("#result-title:text('Regression dashboard')");
  const figures = await page.locator("#content figure h3").allTextContents();
  const regCards = await page.locator("#content .metric").allTextContents();
  const marks = await page.locator("#content figure .mark").count();
  const regShot = await capture(page, "regression-dashboard");
  record("ST-REP-02", "FR-022, UI-05", "Open a regression dashboard",
    "Predicted-vs-actual and residual plots render",
    ["Predicted vs actual", "Residual plot", "Residual histogram"].every((f) => figures.includes(f))
      && regCards.some((c) => c.startsWith("RMSE")) && marks > 0,
    `plots [${figures.join(", ")}] with ${marks} marks; cards ` +
    `${regCards.map((c) => c.replace(/\d.*/, "")).join(", ")}`, regShot);

  // ------------------------------------------------------- ST-REP-03 compare + downloads
  const boxes = rows.locator("input[type=checkbox]");
  await boxes.nth(classification[0][1]).check();
  await boxes.nth(regression).check();
  const mixedMessage = await page.locator("#selection").textContent();
  const mixedDisabled = await page.locator("#compare").isDisabled();
  const mixedShot = await capture(page, "mixed-selection-blocked");
  await boxes.nth(regression).uncheck();
  for (const [, index] of classification.slice(1, 3)) await boxes.nth(index).check();
  await page.click("#compare");
  await page.waitForSelector("#result-title:text('Model comparison')");
  const best = await page.locator("#content td.best").count();
  const headers = await page.locator("#content thead th").allTextContents();
  const compareShot = await capture(page, "comparison");
  const files = {};
  for (const format of ["JSON", "PDF"]) {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.click(`#downloads button:text('Download ${format}')`),
    ]);
    const path = join(evidence, `browser-${download.suggestedFilename()}`);
    await download.saveAs(path);
    files[format] = readFileSync(path);
  }
  const report = JSON.parse(files.JSON.toString());
  const pdfOk = files.PDF.subarray(0, 5).toString() === "%PDF-";
  record("ST-REP-03", "FR-023..027, UI-06", "Compare 3 runs and download PDF and JSON",
    "Best model highlighted; both files download and open; mismatch disables Compare",
    mixedDisabled && /same dataset and task/.test(mixedMessage) && headers.length === 4 &&
      best > 0 && report.evaluations.length === 3 && report.best_per_metric && pdfOk,
    `mixed selection: Compare disabled=${mixedDisabled}, message "${mixedMessage}"; ` +
    `comparison columns [${headers.slice(1).join(", ")}], ${best} best-value cells; JSON ` +
    `report_type=${report.report_type} with ${report.evaluations.length} evaluations; PDF ` +
    `${files.PDF.length} bytes, header ok=${pdfOk}`, `${mixedShot}, ${compareShot}`);

  // ------------------------------------------------------- layout at the minimum viewport
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  record("UI-LAYOUT-1280", "SRS 2.4 (1280x720)", "Layout at the minimum supported viewport",
    "No horizontal page overflow at 1280x720", overflow <= 0,
    `horizontal overflow ${overflow}px at 1280x720`, compareShot);

  // --------------------------------------------------------------------------- sign out
  await page.click("#logout");
  await page.waitForSelector("#login:not([hidden])");
  const leftover = await page.locator("#runs tr, #content *").count();
  await page.reload();
  const afterReload = await page.locator("#history").isHidden();
  const outShot = await capture(page, "signed-out");
  record("ST-AUTH-01(UI sign-out)", "FR-003, UI-01", "Sign out, then reload /results",
    "Login form shown; no protected data on the page", leftover === 0 && afterReload,
    `after sign-out ${leftover} result/history nodes remain; after reload history hidden=` +
    `${afterReload}`, outShot);
  record("UI-CONSOLE", "UI-01..06", "No browser console errors during the run",
    "0 console errors", consoleErrors.length === 0,
    `${consoleErrors.length} console errors ${consoleErrors.slice(0, 3).join(" | ")}; ` +
    `failed resources: ${failedResources.join(", ") || "none"}`);
} catch (error) {
  record("BROWSER-RUN", "-", "Browser script", "completes", false,
    `ERROR ${error.message}`, await capture(page, "error"));
} finally {
  await browser.close();
  writeFileSync(join(evidence, "browser-results.json"), JSON.stringify(
    {environment: {browser: `${names[engine]} ${version} (headless)`, platform: process.platform,
      arch: process.arch, viewport: "1280x720", base}, results}, null, 2) + "\n");
}
process.exit(results.every((r) => r.status === "PASS") ? 0 : 1);
