"""superesp.framework.report — render a head's held-out confusion matrix +
risk-coverage (abstention) curve to markdown + a tiny self-contained HTML.

Pure rendering of numbers already produced by train.evaluate() and
abstain.risk_coverage() — no new measurement, held-out only.
"""
from __future__ import annotations

from pathlib import Path


def write_report(name: str, class_names: list[str], ev: dict, rc: dict, out_dir) -> dict:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    conf = ev["confusion"]
    n = len(class_names)

    # --- markdown ---
    L = [f"# SuperESP head report — {name}\n",
         f"Held-out TEST accuracy: **{ev['test_acc']:.3f}** (n={ev['n_test']})  •  "
         f"abstention AURC **{rc['aurc']:.4f}** (oracle {rc['oracle_aurc']:.4f}, "
         f"random {rc['random_aurc']:.4f})\n",
         "## Confusion matrix (rows = true, cols = predicted)\n",
         "| true \\\\ pred | " + " | ".join(class_names) + " |",
         "|---|" + "|".join("---" for _ in class_names) + "|"]
    for i in range(n):
        row = conf[i]
        cells = " | ".join(f"**{row[j]}**" if i == j else str(row[j]) for j in range(n))
        L.append(f"| {class_names[i]} | {cells} |")
    # per-class recall
    L.append("\n## Per-class recall")
    for i in range(n):
        tot = sum(conf[i]); rec = conf[i][i] / tot if tot else 0.0
        L.append(f"- {class_names[i]}: {rec:.3f} ({conf[i][i]}/{tot})")
    # risk-coverage at a few coverage points
    L.append("\n## Risk vs coverage (abstain on low-margin inputs)")
    cov = rc["coverage"]; risk = rc["risk"]
    L.append("| coverage | risk |")
    L.append("|---|---|")
    for q in (0.5, 0.7, 0.9, 1.0):
        idx = min(range(len(cov)), key=lambda k: abs(cov[k] - q))
        L.append(f"| {cov[idx]:.2f} | {risk[idx]:.3f} |")
    md = out_dir / f"{name}.md"
    md.write_text("\n".join(L))

    # --- tiny self-contained HTML (confusion heat + accuracy) ---
    cells_html = ""
    for i in range(n):
        rowtot = sum(conf[i]) or 1
        cells_html += "<tr><th>" + class_names[i] + "</th>"
        for j in range(n):
            v = conf[i][j]; a = v / rowtot
            bg = f"rgba(34,139,34,{a:.2f})" if i == j else f"rgba(200,60,60,{a:.2f})"
            cells_html += f'<td style="background:{bg};text-align:center">{v}</td>'
        cells_html += "</tr>"
    html = f"""<!doctype html><meta charset=utf-8><title>SuperESP {name}</title>
<body style="font-family:system-ui;max-width:720px;margin:2rem auto">
<h2>SuperESP head — {name}</h2>
<p>Held-out accuracy <b>{ev['test_acc']:.3f}</b> (n={ev['n_test']}) ·
abstention AURC <b>{rc['aurc']:.4f}</b> (oracle {rc['oracle_aurc']:.4f}).</p>
<h3>Confusion (rows=true, cols=pred)</h3>
<table style="border-collapse:collapse" border=1 cellpadding=6>
<tr><th></th>{''.join('<th>'+c+'</th>' for c in class_names)}</tr>{cells_html}</table>
</body>"""
    htmlp = out_dir / f"{name}.html"
    htmlp.write_text(html)
    return {"md": str(md), "html": str(htmlp)}
