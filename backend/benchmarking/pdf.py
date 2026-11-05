"""Render the same stored results used by the browser, without loading model artifacts."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .comparison import is_numeric_metric

INK = colors.HexColor("#182c3a")
ACCENT = colors.HexColor("#08786b")
GRID = colors.HexColor("#d2e1df")


def _chart(title, pairs, *, lines=False, bars=False):
    drawing = Drawing(440, 155)
    points = [point for series in pairs for point in series]
    if not points:
        return drawing
    xs, ys = zip(*points, strict=True)
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = (0, max(ys)) if bars else (min(ys), max(ys))
    drawing.add(Line(36, 24, 416, 24, strokeColor=INK))
    drawing.add(Line(36, 24, 36, 134, strokeColor=INK))
    drawing.add(String(36, 141, title, fillColor=INK, fontSize=9))
    drawing.add(String(36, 9, f"{xmin:.4g} to {xmax:.4g}", fillColor=INK, fontSize=8))
    drawing.add(String(42, 127, f"y: {ymin:.4g} to {ymax:.4g}", fillColor=INK, fontSize=8))
    for index, series in enumerate(pairs):
        color = (ACCENT, colors.HexColor("#365ca0"), colors.HexColor("#9a512e"))[index % 3]
        scaled = [
            (42 + 368 * ((x - xmin) / (xmax - xmin or 1)),
             24 + 96 * ((y - ymin) / (ymax - ymin or 1)))
            for x, y in series
        ]
        if lines and len(scaled) > 1:
            drawing.add(PolyLine([coord for point in scaled for coord in point], strokeColor=color))
        elif bars:
            width = min(30, 350 / len(scaled))
            for x, y in scaled:
                drawing.add(Rect(
                    x - width / 2, 24, width, y - 24, fillColor=color, strokeColor=None,
                ))
        else:
            for x, y in scaled:
                drawing.add(Circle(x, y, 1.7, fillColor=color, strokeColor=None))
    return drawing


def render_pdf(data):
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].splitLongWords = True
    story = []

    def paragraph(value, style="BodyText"):
        return Paragraph(escape(str(value)), styles[style])

    def table(rows, widths):
        story.append(LongTable(
            [[paragraph(cell) for cell in row] for row in rows],
            colWidths=widths, repeatRows=1, splitInRow=1, hAlign="LEFT",
            style=[("BACKGROUND", (0, 0), (-1, 0), GRID), ("VALIGN", (0, 0), (-1, -1), "TOP")],
        ))
        story.append(Spacer(1, 12))

    story.extend([
        paragraph(f"{data['report_type'].title()} report", "Title"),
        paragraph(data["id"]),
        paragraph(f"Generated {data['generated_at']}"),
        paragraph(f"Owner {data['owner']['email']} ({data['owner']['id']})"),
    ])
    results = data["evaluations"]
    if data["report_type"] == "comparison":
        winners = data["best_per_metric"]
        rows = [["Metric", *[f"Model {index}" for index in range(1, len(results) + 1)]]]
        for metric, winner in winners.items():
            rows.append([
                metric.replace("_", " "),
                *[
                    f"{row['metrics'][metric]:.6g}" + (" (best)" if row["id"] == winner else "")
                    for row in results
                ],
            ])
        table(rows, [92] + [360 / len(results)] * len(results))

    for index, result in enumerate(results, 1):
        if data["report_type"] == "comparison":
            story.append(PageBreak())
        story.append(paragraph(f"Model {index} · Evaluation {result['id']}", "Heading2"))
        metadata = [["Field", "Value"]]
        for key in ("task_type", "status", "duration_seconds", "sandbox_image"):
            metadata.append([key.replace("_", " ").title(), result[key]])
        for group in ("model", "dataset"):
            for key, value in result[group].items():
                metadata.append([f"{group.title()} {key.replace('_', ' ')}", value])
        table(metadata, [120, 332])
        metrics = result["metrics"]
        table(
            [
                ["Metric", "Value"],
                *[
                    [name.replace("_", " "), f"{value:.8g}"]
                    for name, value in metrics.items() if is_numeric_metric(value)
                ],
            ],
            [225, 227],
        )
        if metrics.get("roc_auc_note"):
            story.append(paragraph(metrics["roc_auc_note"]))
        if metrics.get("per_class"):
            fields = ("precision", "recall", "f1", "support")
            table([
                ["Class", "Precision", "Recall", "F1", "Support"],
                *[[label, *(f"{values[key]:.6g}" for key in fields)]
                  for label, values in metrics["per_class"].items()],
            ], [116, 84, 84, 84, 84])
        charts = result["charts"]
        if charts.get("confusion_matrix"):
            labels = charts["labels"]
            story.append(paragraph("Confusion matrix (actual rows, predicted columns)", "Heading3"))
            # Split wide matrices into column groups while repeating the actual labels.
            for start in range(0, len(labels), 8):
                stop = start + 8
                group = labels[start:stop]
                table(
                    [["Actual / predicted", *group]] +
                    [[label, *row[start:stop]]
                     for label, row in zip(labels, charts["confusion_matrix"], strict=True)],
                    [100] + [352 / len(group)] * len(group),
                )
        if charts.get("roc"):
            for label, curve in charts["roc"]["curves"].items():
                story.append(paragraph(f"ROC for {label} (AUC {curve['auc']:.4f})"))
                points = list(zip(curve["fpr"], curve["tpr"], strict=True))
                story.append(_chart(
                    "False positive rate / true positive rate", [points], lines=True,
                ))
        if charts.get("predicted_vs_actual"):
            scatter = charts["predicted_vs_actual"]
            residuals = charts["residuals"]
            histogram = charts["residual_histogram"]
            story.extend([
                _chart("Actual / predicted", [list(zip(
                    scatter["actual"], scatter["predicted"], strict=True,
                ))]),
                _chart("Predicted / residual", [list(zip(
                    residuals["predicted"], residuals["residual"], strict=True,
                ))]),
                _chart("Residual / count", [list(zip(
                    histogram["edges"][:-1], histogram["counts"], strict=True,
                ))], bars=True),
            ])
    SimpleDocTemplate(stream, title=f"{data['report_type'].title()} report").build(story)
    return stream.getvalue()
