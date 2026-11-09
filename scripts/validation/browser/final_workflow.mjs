// Run against a disposable demo stack with FINAL_FIXTURES and FINAL_ROLE_ACCOUNTS set.
// Credentials are read from a private local file and are never written to evidence.
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, firefox } from 'playwright-core';

const base = process.env.BASE_URL ?? 'http://localhost:5173';
const fixtures = process.env.FINAL_FIXTURES;
if (!fixtures) throw new Error('Set FINAL_FIXTURES to the directory with iris.joblib, iris.csv and wine.csv.');
const evidence = resolve(process.env.FINAL_EVIDENCE ?? 'docs/evidence/final/browser');
mkdirSync(evidence, { recursive: true });
const engine = process.env.BROWSER ?? 'chrome';
const browser = engine === 'firefox'
  ? await firefox.launch({ headless: true })
  : await chromium.launch({ channel: engine, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, acceptDownloads: true });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
const results = [];
const email = `demo-${randomBytes(6).toString('hex')}@example.org`;
const password = `${randomBytes(16).toString('base64url')}Aa1!`;
async function record(id, description, run) {
  try {
    await run();
    const screenshot = `${id.replaceAll(/[^a-zA-Z0-9-]/g, '-')}.png`;
    await page.screenshot({ path: join(evidence, screenshot), fullPage: true });
    results.push({ id, description, status: 'PASS', screenshot });
    console.log(`PASS ${id}`);
  } catch (error) {
    await page.screenshot({ path: join(evidence, `${id}-failure.png`), fullPage: true });
    results.push({ id, description, status: 'FAIL', actual: error.message });
    throw error;
  }
}
let auth;
async function api(path, method = 'GET', body) {
  const response = await context.request.fetch(`${base}/api/v1${path}`, {
    method, headers: { Authorization: `Bearer ${auth}` }, data: body,
  });
  assert.ok(response.ok(), `${method} ${path}: HTTP ${response.status()}`);
  return response.status() === 204 ? null : response.json();
}
async function waitRun(id) {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const result = await api(`/evaluations/${id}/status`);
    if (result.status === 'SUCCEEDED') return;
    assert.ok(['QUEUED', 'RUNNING'].includes(result.status), result.error_message);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('Evaluation did not complete within 90 seconds.');
}
try {
  await record('ST-AUTH-01-register', 'Register and sign in through React', async () => {
    await page.goto(`${base}/register`);
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: /register|create account/i }).click();
    await page.waitForURL('**/upload');
    await page.getByRole('heading', { name: 'New evaluation' }).waitFor();
    const login = await context.request.post(`${base}/api/v1/auth/login`, { data: { email, password } });
    assert.equal(login.status(), 200);
    auth = (await login.json()).access;
  });
  let id;
  await record('ST-ING-01', 'Upload model and CSV, then validate compatibility', async () => {
    await page.getByLabel('Model file').setInputFiles(join(fixtures, 'iris.joblib'));
    await page.getByText('Uploaded: iris.joblib', { exact: false }).waitFor();
    await page.getByLabel('CSV dataset').setInputFiles(join(fixtures, 'iris.csv'));
    await page.getByText('Uploaded: iris.csv', { exact: false }).waitFor();
    await page.getByRole('button', { name: 'Run compatibility check' }).click();
    await page.getByRole('heading', { name: 'Compatible', exact: true }).waitFor({ timeout: 60000 });
  });
  await record('ST-EXE-01', 'Run inference in a real sandbox and render classification', async () => {
    await page.getByRole('button', { name: 'Start evaluation' }).click();
    await page.waitForURL('**/evaluations/*');
    id = page.url().split('/').at(-1);
    await page.getByRole('heading', { name: 'SUCCEEDED', exact: true }).waitFor({ timeout: 120000 });
    await page.getByRole('heading', { name: 'Confusion matrix' }).waitFor();
    const roc = page.getByLabel('ROC class');
    if (await roc.count()) {
      const options = await roc.locator('option').evaluateAll((items) => items.map((item) => item.value));
      if (options.length > 1) await roc.selectOption(options[1]);
    }
  });
  await record('ST-REP-exports', 'Download parseable JSON and PDF from the React result', async () => {
    for (const format of ['JSON', 'PDF']) {
      const pending = page.waitForEvent('download');
      await page.getByRole('button', { name: `Download ${format}` }).click();
      const download = await pending;
      const path = join(evidence, `evaluation.${format.toLowerCase()}`);
      await download.saveAs(path);
      const bytes = readFileSync(path);
      if (format === 'JSON') assert.equal(JSON.parse(bytes.toString()).evaluations[0].id, id);
      else assert.equal(bytes.subarray(0, 4).toString(), '%PDF');
    }
  });
  const detail = await api(`/evaluations/${id}`);
  const second = await api('/evaluations', 'POST', { model_id: detail.model_id, dataset_id: detail.dataset_id });
  await waitRun(second.id);
  await record('ST-REP-comparison', 'Refresh session, compare two compatible evaluations and export', async () => {
    await page.goto(`${base}/history`);
    await page.reload();
    await page.getByRole('link', { name: 'Open', exact: true }).first().waitFor();
    await page.getByLabel(`Select run ${id}`, { exact: true }).check();
    await page.getByLabel(`Select run ${second.id}`, { exact: true }).check();
    await page.getByRole('button', { name: 'Compare selected (2)' }).click();
    await page.getByRole('heading', { name: 'Comparison', exact: true }).waitFor();
    assert.ok(await page.getByText('· best', { exact: false }).count());
    const pending = page.waitForEvent('download');
    await page.getByRole('button', { name: 'PDF', exact: true }).click();
    await (await pending).saveAs(join(evidence, 'comparison.pdf'));
  });
  await record('ST-AUTH-02', 'Filter history, cancel deletion, delete and preserve remaining shared run', async () => {
    await page.getByLabel('Filter task').selectOption('REGRESSION');
    await page.getByText('No evaluations found.').waitFor();
    await page.getByLabel('Filter task').selectOption('');
    await page.getByRole('button', { name: `Delete run ${second.id}`, exact: true }).click();
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    assert.equal((await api(`/evaluations/${second.id}`)).id, second.id);
    await page.getByRole('button', { name: `Delete run ${second.id}`, exact: true }).click();
    await page.getByRole('button', { name: 'Confirm delete', exact: true }).click();
    await page.getByRole('alertdialog').waitFor({ state: 'hidden' });
    await page.getByRole('button', { name: `Delete run ${second.id}`, exact: true }).waitFor({ state: 'hidden' });
    assert.equal((await api(`/evaluations/${id}`)).id, id);
  });
  await record('ST-ING-negative', 'Reject unsupported upload and incompatible dataset', async () => {
    await page.goto(`${base}/upload`);
    await page.getByLabel('Model file').setInputFiles({ name: 'unsafe.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('invalid') });
    await page.getByRole('alert').filter({ hasText: 'Model must be' }).waitFor();
    await page.getByLabel('Model file').setInputFiles(join(fixtures, 'iris.joblib'));
    await page.getByText('Uploaded: iris.joblib', { exact: false }).waitFor();
    await page.getByLabel('CSV dataset').setInputFiles(join(fixtures, 'wine.csv'));
    await page.getByText('Uploaded: wine.csv', { exact: false }).waitFor();
    await page.getByRole('button', { name: 'Run compatibility check' }).click();
    await page.getByRole('heading', { name: 'Compatibility failed' }).waitFor({ timeout: 60000 });
    assert.equal(await page.getByRole('button', { name: 'Start evaluation' }).isDisabled(), true);
  });
  await record('UI-responsive', '375-pixel workflow has no horizontal overflow', async () => {
    await page.setViewportSize({ width: 375, height: 812 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    assert.equal(overflow, false);
    await page.setViewportSize({ width: 1280, height: 800 });
  });
  await record('ST-AUTH-01-logout', 'Sign out and block protected history', async () => {
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await page.waitForURL('**/login');
    await page.goto(`${base}/history`);
    await page.waitForURL('**/login');
  });
  if (process.env.FINAL_ROLE_ACCOUNTS) {
    const roles = JSON.parse(readFileSync(process.env.FINAL_ROLE_ACCOUNTS, 'utf8'));
    for (const [role, credentials] of Object.entries(roles)) {
      await record(`UI-${role}`, `${role} controls and role-specific API access`, async () => {
        await page.goto(`${base}/login`);
        await page.getByLabel('Email', { exact: true }).fill(credentials.email);
        await page.getByLabel('Password', { exact: true }).fill(credentials.password);
        await page.getByRole('button', { name: 'Sign in', exact: true }).click();
        await page.waitForURL('**/upload');
        if (role === 'admin') {
          await page.getByRole('link', { name: 'Administration', exact: true }).click();
          await page.getByRole('heading', { name: 'Security audit' }).waitFor();
          await page.getByLabel('Search accounts').fill(email);
          await page.getByRole('button', { name: 'Search', exact: true }).click();
          await page.getByRole('cell', { name: email, exact: true }).waitFor();
          await page.getByRole('row').filter({ has: page.getByRole('cell', { name: email, exact: true }) }).getByRole('button', { name: 'Deactivate', exact: true }).click();
          await page.getByRole('status').filter({ hasText: 'deactivated' }).waitFor();
          await page.getByRole('row').filter({ has: page.getByRole('cell', { name: email, exact: true }) }).getByRole('button', { name: 'Activate', exact: true }).click();
          await page.getByRole('status').filter({ hasText: 'activated' }).waitFor();
        } else {
          await page.getByRole('link', { name: 'Workspaces', exact: true }).click();
          await page.getByLabel('Workspace name').fill(`Demo ${Date.now()}`);
          await page.getByRole('button', { name: 'Create', exact: true }).click();
          await page.getByRole('status').filter({ hasText: 'Workspace created' }).waitFor();
          await page.getByLabel('Member email').fill(email);
          await page.getByRole('button', { name: 'Add member', exact: true }).click();
          await page.getByRole('status').filter({ hasText: 'member added' }).waitFor();
        }
        await page.screenshot({ path: join(evidence, `UI-${role}-controls.png`), fullPage: true });
        await page.getByRole('button', { name: 'Sign out', exact: true }).click();
        await page.waitForURL('**/login');
      });
    }
  }
  assert.deepEqual(errors, []);
} finally {
  writeFileSync(join(evidence, 'results.json'), JSON.stringify({ executed_at: new Date().toISOString(), browser: engine, base_url: base, results, browser_errors: errors }, null, 2));
  await browser.close();
}
