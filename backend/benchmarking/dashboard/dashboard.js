const byId = (id) => document.getElementById(id);
const selected = new Map();
let access;
let refresh;
let page = 1;
let busy = false;

const names = {
  accuracy: "Accuracy", precision_macro: "Macro precision", recall_macro: "Macro recall",
  f1_macro: "Macro F1", precision_weighted: "Weighted precision",
  recall_weighted: "Weighted recall", f1_weighted: "Weighted F1", roc_auc: "ROC AUC",
  mae: "MAE", mse: "MSE", rmse: "RMSE", r2: "R²", n_samples: "Samples",
};
const format = (value) => Number.isFinite(value) ? Number(value.toPrecision(5)).toString() : "—";

function element(tag, value, parent, className) {
  const node = document.createElement(tag);
  if (value != null) node.textContent = value;
  if (className) node.className = className;
  parent?.append(node);
  return node;
}

function svgNode(tag, attributes, parent, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text != null) node.textContent = text;
  parent.append(node);
  return node;
}

function notice(message = "") {
  byId("notice").textContent = message;
}

async function api(path, payload, download = false) {
  const headers = {};
  if (access) headers.Authorization = `Bearer ${access}`;
  if (payload) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1/${path}`, {
    headers, method: payload ? "POST" : "GET", body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))).error;
    const details = Array.isArray(problem?.details) ? problem.details : [];
    throw new Error(details[0]?.messages?.[0] || problem?.message || `Request failed (${response.status}).`);
  }
  if (download) return response.blob();
  return response.status === 204 ? null : response.json();
}

async function action(callback) {
  if (busy) return;
  busy = true;
  notice();
  try {
    await callback();
  } catch (error) {
    notice(error.message);
  } finally {
    busy = false;
  }
}

function updateSelection() {
  const runs = [...selected.values()];
  const incomplete = runs.some((run) => !run.dataset_sha256 || !run.task_type);
  const mismatch = new Set(runs.map((run) => run.dataset_sha256)).size > 1
    || new Set(runs.map((run) => run.task_type)).size > 1;
  let message = `${runs.length} selected. Select 2–5 runs to compare.`;
  if (incomplete) message = "A selected run is missing its dataset checksum or task type.";
  else if (mismatch) message = "Select runs with the same dataset and task type.";
  byId("selection").textContent = message;
  byId("compare").disabled = incomplete || mismatch || runs.length < 2;
  for (const box of byId("runs").querySelectorAll("input")) {
    box.disabled = !box.checked && runs.length >= 5;
  }
}

function table(parent, columns) {
  const root = element("table", null, element("div", null, parent, "scroll"));
  const header = element("tr", null, element("thead", null, root));
  for (const column of columns) element("th", column, header).scope = "col";
  return element("tbody", null, root);
}

async function loadRuns(number = 1) {
  const data = await api(`evaluations?status=SUCCEEDED&page=${number}`);
  page = number;
  const runs = byId("runs");
  runs.replaceChildren();
  if (!data.results.length) element("p", "No completed runs yet.", runs);
  else {
    const body = table(runs, ["Select", "Evaluation", "Task", "Created"]);
    for (const run of data.results) {
      const row = element("tr", null, body);
      const box = element("input", null, element("td", null, row));
      box.type = "checkbox";
      box.checked = selected.has(run.id);
      box.setAttribute("aria-label", `Select evaluation ${run.id}`);
      box.onchange = () => {
        if (box.checked) selected.set(run.id, run);
        else selected.delete(run.id);
        updateSelection();
      };
      const open = element("button", run.id, element("td", null, row));
      open.onclick = () => action(async () => {
        const detail = await api(`evaluations/${run.id}`);
        const chart = await api(`evaluations/${run.id}/charts`);
        renderEvaluation(detail, chart.charts ?? {});
      });
      element("td", run.task_type.toLowerCase(), row);
      element("td", new Date(run.created_at).toLocaleString(), row);
    }
  }
  byId("page").textContent = `Page ${page}`;
  byId("previous").disabled = !data.previous;
  byId("next").disabled = !data.next;
  updateSelection();
}

function resultPanel(title, kind, id) {
  byId("result").hidden = false;
  byId("result-title").textContent = title;
  const downloads = byId("downloads");
  downloads.replaceChildren();
  for (const format of ["json", "pdf"]) {
    const button = element("button", `Download ${format.toUpperCase()}`, downloads);
    button.onclick = () => action(async () => {
      const blob = await api(`${kind}s/${id}/report.${format}`, undefined, true);
      const url = URL.createObjectURL(blob);
      const link = element("a");
      link.href = url;
      link.download = `${kind}-${id}.${format}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  const content = byId("content");
  content.replaceChildren();
  byId("result-title").focus();
  return content;
}

function plot(parent, title, xs, ys, xName, yName, mode = "scatter") {
  const chart = element("figure", null, parent);
  element("h3", title, chart);
  const svg = svgNode("svg", {viewBox: "0 0 420 222", role: "img", "aria-label": title}, chart);
  const bounded = mode === "line";
  const xMin = bounded ? 0 : Math.min(...xs);
  const xMax = bounded ? 1 : Math.max(...xs);
  const yMin = bounded || mode === "bars" ? 0 : Math.min(...ys);
  const yMax = bounded ? 1 : Math.max(...ys);
  const scale = (value, min, max) => max === min ? .5 : (value - min) / (max - min);
  const points = xs.map((x, i) => [55 + 335 * scale(x, xMin, xMax), 168 - 150 * scale(ys[i], yMin, yMax)]);
  for (const ratio of [0, .25, .5, .75, 1]) {
    const y = 168 - 150 * ratio;
    svgNode("line", {x1: 50, x2: 397, y1: y, y2: y, class: "axis"}, svg);
    svgNode("text", {x: 46, y: y + 3, "text-anchor": "end"}, svg, format(yMin + (yMax - yMin) * ratio));
    const x = 55 + 335 * ratio;
    svgNode("text", {x, y: 187, "text-anchor": "middle"}, svg, format(xMin + (xMax - xMin) * ratio));
  }
  svgNode("text", {x: 222, y: 209, "text-anchor": "middle"}, svg, xName);
  svgNode("text", {x: 10, y: 92, transform: "rotate(-90 10 92)", "text-anchor": "middle"}, svg, yName);
  if (bounded) {
    svgNode("polyline", {points: points.map((point) => point.join(",")).join(" "), class: "curve"}, svg);
  } else {
    const width = Math.min(32, 310 / points.length);
    points.forEach(([x, y], i) => {
      const mark = mode === "bars"
        ? svgNode("rect", {x: x - width / 2, y, width, height: 168 - y, class: "mark"}, svg)
        : svgNode("circle", {cx: x, cy: y, r: 2.6, class: "mark"}, svg);
      svgNode("title", {}, mark, `${xName} ${format(xs[i])}, ${yName} ${format(ys[i])}`);
    });
  }
}

function renderEvaluation(detail, charts) {
  const title = detail.task_type === "REGRESSION" ? "Regression dashboard" : "Classification dashboard";
  const parent = resultPanel(title, "evaluation", detail.id);
  element("p", detail.id, parent);
  const metrics = detail.metrics_json ?? {};
  const cards = element("div", null, parent, "metrics");
  for (const [key, label] of Object.entries(names)) {
    if (!(key in metrics)) continue;
    const card = element("div", label, cards, "metric");
    element("strong", format(metrics[key]), card);
  }
  if (!Object.keys(charts).length) element("p", "This evaluation has no stored charts.", parent);
  if (metrics.roc_auc_note) element("p", metrics.roc_auc_note, parent);
  if (charts.confusion_matrix?.length) {
    element("h3", "Confusion matrix", parent);
    const body = table(parent, ["Actual / predicted", ...charts.labels]);
    charts.confusion_matrix.forEach((values, index) => {
      const row = element("tr", null, body);
      element("th", charts.labels[index], row).scope = "row";
      values.forEach((value) => element("td", value, row));
    });
  }
  if (charts.roc) {
    const label = element("label", "ROC class ", parent);
    const picker = element("select", null, label);
    const classes = Object.keys(charts.roc.curves);
    classes.forEach((name) => { element("option", name, picker).value = name; });
    const holder = element("div", null, parent, "plots");
    const show = () => {
      holder.replaceChildren();
      const curve = charts.roc.curves[picker.value];
      plot(holder, `ROC curve (AUC ${format(curve.auc)})`, curve.fpr, curve.tpr,
        "False positive rate", "True positive rate", "line");
    };
    picker.onchange = show;
    show();
  }
  if (metrics.per_class) {
    element("h3", "Per-class metrics", parent);
    const body = table(parent, ["Class", "Precision", "Recall", "F1", "Support"]);
    for (const [label, scores] of Object.entries(metrics.per_class)) {
      const row = element("tr", null, body);
      element("th", label, row).scope = "row";
      for (const key of ["precision", "recall", "f1", "support"]) {
        element("td", format(scores[key]), row);
      }
    }
  }
  if (charts.predicted_vs_actual) {
    const {predicted_vs_actual: scatter, residuals, residual_histogram: histogram} = charts;
    if (scatter.sampled) element("p", "Scatter plots show a sample of the evaluation rows.", parent);
    const plots = element("div", null, parent, "plots");
    plot(plots, "Predicted vs actual", scatter.actual, scatter.predicted, "Actual", "Predicted");
    plot(plots, "Residual plot", residuals.predicted, residuals.residual, "Predicted", "Residual");
    plot(plots, "Residual histogram", histogram.edges.slice(0, -1), histogram.counts,
      "Residual bin start", "Count", "bars");
  }
}

function renderComparison(data) {
  const parent = resultPanel("Model comparison", "comparison", data.id);
  const models = data.evaluations;
  const body = table(parent, ["Metric", ...models.map((run, i) => run.model.filename || `Model ${i + 1}`)]);
  const identifiers = element("tr", null, body);
  element("th", "Evaluation", identifiers).scope = "row";
  models.forEach((run) => element("td", run.id, identifiers));
  const metrics = new Set(models.flatMap((run) => Object.keys(run.metrics).filter((key) => key in names)));
  for (const metric of metrics) {
    const row = element("tr", null, body);
    element("th", names[metric], row).scope = "row";
    for (const run of models) {
      const best = data.best_per_metric[metric] === run.id;
      element("td", format(run.metrics[metric]) + (best ? " (best)" : ""), row, best ? "best" : null);
    }
  }
}

byId("login").onsubmit = (event) => {
  event.preventDefault();
  action(async () => {
    const credentials = Object.fromEntries(new FormData(event.target));
    const session = await api("auth/login", credentials);
    access = session.access;
    refresh = session.refresh;
    try {
      await loadRuns();
    } catch (error) {
      access = refresh = undefined;
      throw error;
    }
    event.target.reset();
    event.target.hidden = true;
    byId("logout").hidden = byId("history").hidden = false;
  });
};

byId("logout").onclick = () => action(async () => {
  try {
    await api("auth/logout", {refresh});
  } finally {
    access = refresh = undefined;
    selected.clear();
    for (const id of ["runs", "downloads", "content"]) byId(id).replaceChildren();
    for (const id of ["logout", "history", "result"]) byId(id).hidden = true;
    byId("login").hidden = false;
  }
});
byId("previous").onclick = () => action(() => loadRuns(page - 1));
byId("next").onclick = () => action(() => loadRuns(page + 1));
byId("compare").onclick = () => action(async () => {
  renderComparison(await api("comparisons", {evaluation_ids: [...selected.keys()]}));
});
