#!/usr/bin/env python3
"""Gera um relatório HTML local a partir do JSON produzido por inference.py.

Sem dependências extras: usa apenas a biblioteca padrão do Python.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from urllib.parse import quote


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera uma página HTML visual para apresentar uma inferência YOLO."
    )
    parser.add_argument("json_file", type=Path, help="JSON produzido por inference.py")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="HTML de saída. Padrão: <json>_report.html",
    )
    return parser


def default_output_path(json_file: Path) -> Path:
    return json_file.with_name(f"{json_file.stem}_report.html")


def asset_url(asset: str | Path, report_path: Path) -> str:
    asset_path = Path(asset).resolve()
    rel = os.path.relpath(asset_path, report_path.parent.resolve())
    return quote(Path(rel).as_posix())


def fmt_ms(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f} ms"


def detection_rows(detections: list[dict]) -> str:
    if not detections:
        return (
            '<div class="empty">Nenhuma detecção acima do limiar de confiança. '
            'Isso continua sendo um resultado válido para o modelo cru.</div>'
        )

    rows = []
    for index, det in enumerate(detections, start=1):
        bbox = det["bbox_xyxy"]
        center = det["center_px"]
        error = det["error_from_image_center_px"]
        confidence = float(det["confidence"])
        conf_pct = confidence * 100.0
        class_name = html.escape(str(det["class_name"]))
        rows.append(
            f"""
            <tr>
              <td><strong>{index}</strong></td>
              <td><span class="class-chip">{class_name}</span><br><small>ID {det['class_id']}</small></td>
              <td>
                <strong>{conf_pct:.1f}%</strong>
                <div class="bar"><span style="width:{max(0.0, min(100.0, conf_pct)):.1f}%"></span></div>
              </td>
              <td>x1={bbox['x1']:.1f}<br>y1={bbox['y1']:.1f}<br>x2={bbox['x2']:.1f}<br>y2={bbox['y2']:.1f}</td>
              <td>cx={center['x']:.1f}<br>cy={center['y']:.1f}</td>
              <td>ex={error['x']:.1f}<br>ey={error['y']:.1f}</td>
            </tr>
            """
        )

    return f"""
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Classe</th>
            <th>Confiança</th>
            <th>Bounding box</th>
            <th>Centro</th>
            <th>Erro ao centro</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


def render_report(data: dict, report_path: Path) -> str:
    detections = data.get("detections", [])
    timing = data.get("timing_ms", {})
    image_size = data.get("image_size", {})
    params = data.get("parameters", {})

    inference_ms = timing.get("inference")
    fps = None
    if inference_ms is not None and float(inference_ms) > 0:
        fps = 1000.0 / float(inference_ms)

    input_url = asset_url(data["input_image"], report_path)
    output_url = asset_url(data["output_image"], report_path)

    model = html.escape(str(data.get("model", "—")))
    device = html.escape(str(params.get("device", "—")))
    width = image_size.get("width", "—")
    height = image_size.get("height", "—")
    conf = float(params.get("confidence", 0.0))

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HARPia · YOLO Inference Demo</title>
<style>
:root {{
  color-scheme: dark;
  --bg:#0b1020;
  --panel:#121a2d;
  --panel2:#18233b;
  --text:#eef3ff;
  --muted:#9eb0cf;
  --line:#2b3b5f;
  --accent:#66e3b4;
  --accent2:#6db7ff;
  --warn:#ffd479;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:linear-gradient(180deg,#0b1020,#0d1426 45%,#0b1020); color:var(--text); font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
main {{ max-width:1400px; margin:auto; padding:28px; }}
header {{ display:flex; gap:20px; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; margin-bottom:22px; }}
h1 {{ margin:0; font-size:clamp(28px,4vw,48px); letter-spacing:-.04em; }}
.subtitle {{ color:var(--muted); max-width:850px; margin-top:8px; }}
.badge {{ display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border:1px solid var(--line); border-radius:999px; color:var(--accent); background:#0e1728; font-weight:700; }}
.grid {{ display:grid; gap:16px; }}
.metrics {{ grid-template-columns:repeat(6,minmax(0,1fr)); margin-bottom:18px; }}
.card {{ background:rgba(18,26,45,.94); border:1px solid var(--line); border-radius:16px; padding:16px; min-width:0; }}
.metric-label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
.metric-value {{ font-size:22px; font-weight:800; margin-top:5px; overflow-wrap:anywhere; }}
.visuals {{ grid-template-columns:1fr 1fr; margin-bottom:18px; }}
.image-card {{ overflow:hidden; padding:0; }}
.image-card h2 {{ margin:0; padding:14px 16px; font-size:16px; border-bottom:1px solid var(--line); }}
.image-wrap {{ background:#050912; aspect-ratio:4/3; display:grid; place-items:center; }}
.image-wrap img {{ width:100%; height:100%; object-fit:contain; display:block; }}
.section-title {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin:26px 0 10px; }}
.section-title h2 {{ margin:0; font-size:20px; }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:16px; }}
table {{ width:100%; border-collapse:collapse; min-width:800px; background:var(--panel); }}
th,td {{ text-align:left; padding:13px 14px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; background:var(--panel2); }}
tr:last-child td {{ border-bottom:0; }}
small {{ color:var(--muted); }}
.class-chip {{ display:inline-block; border-radius:999px; padding:4px 9px; color:#07140f; background:var(--accent); font-weight:800; }}
.bar {{ width:120px; max-width:100%; height:6px; background:#25314d; border-radius:99px; margin-top:7px; overflow:hidden; }}
.bar span {{ display:block; height:100%; background:var(--accent2); border-radius:99px; }}
.empty {{ padding:20px; border:1px dashed var(--line); border-radius:14px; color:var(--muted); background:var(--panel); }}
.note {{ margin-top:18px; padding:15px 16px; border-left:4px solid var(--warn); background:#17182a; border-radius:10px; color:#dce5f8; }}
.pipeline {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; color:var(--muted); margin-top:10px; }}
.pipeline b {{ color:var(--text); background:var(--panel2); border:1px solid var(--line); padding:6px 9px; border-radius:9px; }}
footer {{ color:var(--muted); margin:26px 0 8px; font-size:13px; }}
@media (max-width:1000px) {{ .metrics {{ grid-template-columns:repeat(3,1fr); }} }}
@media (max-width:760px) {{ main {{ padding:16px; }} .visuals {{ grid-template-columns:1fr; }} .metrics {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <div class="badge">HARPia · demonstração local</div>
      <h1>YOLO Inference</h1>
      <div class="subtitle">Visualização da mesma inferência executada pelo <code>inference.py</code>. A página não executa outro detector: ela apresenta, de forma visual, o resultado já produzido pelo modelo cru.</div>
    </div>
  </header>

  <section class="grid metrics">
    <div class="card"><div class="metric-label">Modelo</div><div class="metric-value">{model}</div></div>
    <div class="card"><div class="metric-label">Device</div><div class="metric-value">{device}</div></div>
    <div class="card"><div class="metric-label">Imagem</div><div class="metric-value">{width}×{height}</div></div>
    <div class="card"><div class="metric-label">Conf. mínima</div><div class="metric-value">{conf:.2f}</div></div>
    <div class="card"><div class="metric-label">Detecções</div><div class="metric-value">{len(detections)}</div></div>
    <div class="card"><div class="metric-label">Inferência</div><div class="metric-value">{fmt_ms(inference_ms)}{f'<br><small>≈ {fps:.2f} FPS</small>' if fps else ''}</div></div>
  </section>

  <section class="grid visuals">
    <article class="card image-card">
      <h2>1 · Imagem original</h2>
      <div class="image-wrap"><img src="{input_url}" alt="Imagem original usada na inferência"></div>
    </article>
    <article class="card image-card">
      <h2>2 · Resultado YOLO</h2>
      <div class="image-wrap"><img src="{output_url}" alt="Imagem anotada pelo YOLO"></div>
    </article>
  </section>

  <div class="section-title"><h2>Detecções</h2><span class="badge">modelo pré-treinado cru</span></div>
  {detection_rows(detections)}

  <div class="note"><strong>Como apresentar:</strong> a classe prevista pelo modelo cru ainda não representa necessariamente a classe real da missão. O objetivo desta etapa é comprovar o pipeline de inferência: imagem → modelo → bbox/confiança → centro → erro visual → saída anotada.</div>

  <div class="section-title"><h2>Pipeline demonstrado</h2></div>
  <div class="pipeline"><b>imagem</b> → <b>YOLO11n</b> → <b>classe + confiança + bbox</b> → <b>cx/cy</b> → <b>ex/ey</b> → <b>imagem + JSON</b></div>

  <footer>Relatório gerado localmente por <code>visual_report.py</code>. Nenhuma dependência web externa é necessária.</footer>
</main>
</body>
</html>
"""


def main() -> int:
    args = build_parser().parse_args()
    if not args.json_file.is_file():
        raise SystemExit(f"ERRO: JSON não encontrado: {args.json_file}")

    report_path = args.output or default_output_path(args.json_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(args.json_file.read_text(encoding="utf-8"))
    report_path.write_text(render_report(data, report_path), encoding="utf-8")
    print(f"Relatório HTML salvo em: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
