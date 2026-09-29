#!/usr/bin/env python3
"""Gera um painel HTML local para a POC de detecção de pessoas em vídeo."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path
from urllib.parse import quote


DEFAULT_METRICS = Path("results/yolo11n_metrics.json")
DEFAULT_COMPARISON = Path("results/comparison.csv")
DEFAULT_SOURCE = Path("results/video_source.json")
DEFAULT_OUTPUT = Path("output/video_report.html")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera um painel HTML local com vídeo, métricas, evidências e log."
    )
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--video", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--log-lines", type=int, default=120)
    return parser


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def asset_url(asset: str | Path, report_path: Path) -> str:
    asset_path = Path(asset).resolve()
    relative = os.path.relpath(asset_path, report_path.parent.resolve())
    return quote(Path(relative).as_posix())


def fmt(value: object, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}"
    return html.escape(str(value))


def read_comparison(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_log_tail(path: Path | None, lines: int) -> str:
    if path is None or not path.is_file() or lines <= 0:
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def metric_card(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<small>{html.escape(detail)}</small>" if detail else ""
    return (
        '<div class="card metric">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>{detail_html}</div>'
    )


def comparison_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return '<p class="muted">Arquivo de comparação não encontrado.</p>'

    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(row.get('model', '—'))}</td>"
            f"<td>{fmt(float(row['processing_fps'])) if row.get('processing_fps') else '—'}</td>"
            f"<td>{fmt(float(row['mean_ms_per_frame']), 1) if row.get('mean_ms_per_frame') else '—'}</td>"
            f"<td>{html.escape(row.get('total_person_detections', '—'))}</td>"
            f"<td>{fmt(float(row['mean_confidence']), 4) if row.get('mean_confidence') else '—'}</td>"
            f"<td>{fmt(float(row['model_size_mb']), 2) if row.get('model_size_mb') else '—'}</td>"
            "</tr>"
        )

    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Modelo</th><th>FPS</th><th>ms/frame</th><th>Detecções</th>"
        "<th>Conf. média</th><th>MB</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def evidence_gallery(metrics: dict, report_path: Path) -> str:
    examples = metrics.get("examples", [])
    if not examples:
        return '<p class="muted">Nenhum frame de evidência registrado.</p>'

    cards = []
    for example in examples:
        path = Path(example)
        cards.append(
            '<figure class="evidence">'
            f'<img src="{asset_url(path, report_path)}" alt="{html.escape(path.name)}">'
            f"<figcaption>{html.escape(path.name)}</figcaption>"
            "</figure>"
        )
    return f'<div class="gallery">{"".join(cards)}</div>'


def render_report(
    metrics: dict,
    comparison: list[dict[str, str]],
    source: dict,
    report_path: Path,
    video_path: Path,
    log_path: Path | None,
    log_lines: int,
) -> str:
    video = metrics["video"]
    timing = metrics["timing"]
    detections = metrics["detections"]
    params = metrics["parameters"]

    source_fps = float(video["original_fps"])
    processing_fps = float(timing["processing_fps"])
    realtime_ratio = source_fps / processing_fps if processing_fps > 0 else 0.0
    log_tail = read_log_tail(log_path, log_lines)

    if video_path.is_file():
        video_block = (
            '<video controls preload="metadata">'
            f'<source src="{asset_url(video_path, report_path)}" type="video/mp4">'
            "Seu navegador não suporta vídeo HTML5."
            "</video>"
        )
    else:
        video_block = (
            '<div class="empty">Vídeo anotado ainda não está disponível neste caminho: '
            f"<code>{html.escape(str(video_path))}</code></div>"
        )

    log_block = (
        f"<pre>{html.escape(log_tail)}</pre>"
        if log_tail
        else '<div class="empty">Nenhum log foi anexado ao relatório.</div>'
    )

    source_url = source.get("url")
    source_title = html.escape(str(source.get("title", "Fonte de vídeo")))
    if source_url:
        source_link = (
            f'<a href="{html.escape(str(source_url), quote=True)}" '
            f'target="_blank" rel="noreferrer">{source_title}</a>'
        )
    else:
        source_link = source_title

    metrics_cards = "".join(
        [
            metric_card("Modelo", str(metrics.get("model", "—"))),
            metric_card("Frames", str(video.get("processed_frames", "—"))),
            metric_card("FPS fonte", fmt(source_fps, 3)),
            metric_card("FPS processamento", fmt(processing_fps, 3)),
            metric_card("ms/frame", fmt(timing.get("mean_ms_per_frame"), 1)),
            metric_card("Detecções person", str(detections.get("total_person_detections", "—"))),
            metric_card("Conf. média", fmt(detections.get("mean_confidence"), 4)),
            metric_card("Tempo total", f"{fmt(timing.get('processing_seconds'), 1)} s"),
        ]
    )

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HARPia · YOLO Video POC</title>
<style>
:root {{
  color-scheme: dark;
  --bg:#09111f; --panel:#111c2f; --panel2:#17243a; --text:#edf4ff;
  --muted:#9eb0cb; --line:#2b3c5f; --accent:#68e6b4; --accent2:#73b8ff;
  --warn:#ffd47a;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; color:var(--text); background:linear-gradient(180deg,#08101d,#0c1628);
  font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
}}
main {{ max-width:1400px; margin:auto; padding:28px; }}
header {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-end; flex-wrap:wrap; }}
h1 {{ font-size:clamp(30px,5vw,52px); margin:6px 0; letter-spacing:-.04em; }}
h2 {{ margin:28px 0 10px; }}
a {{ color:var(--accent2); }}
.badge {{
  display:inline-block; border:1px solid var(--line); background:#0c1729; color:var(--accent);
  padding:7px 11px; border-radius:999px; font-weight:700;
}}
.muted {{ color:var(--muted); }}
.metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:22px 0; }}
.card {{ background:rgba(17,28,47,.96); border:1px solid var(--line); border-radius:15px; padding:16px; }}
.metric .label {{ color:var(--muted); text-transform:uppercase; font-size:11px; letter-spacing:.08em; }}
.metric .value {{ font-size:22px; font-weight:800; margin-top:3px; }}
.metric small {{ display:block; color:var(--muted); margin-top:3px; }}
.panel {{ background:rgba(17,28,47,.96); border:1px solid var(--line); border-radius:16px; padding:16px; }}
video {{ width:100%; max-height:720px; background:#000; border-radius:10px; }}
.gallery {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
.evidence {{ margin:0; overflow:hidden; border:1px solid var(--line); border-radius:14px; background:var(--panel); }}
.evidence img {{ width:100%; display:block; }}
.evidence figcaption {{ padding:8px 11px; color:var(--muted); }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:14px; }}
table {{ width:100%; border-collapse:collapse; min-width:700px; }}
th,td {{ padding:11px 13px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ background:var(--panel2); color:var(--muted); font-size:11px; text-transform:uppercase; }}
pre {{
  max-height:420px; overflow:auto; background:#050a13; border:1px solid var(--line);
  border-radius:12px; padding:14px; white-space:pre-wrap; word-break:break-word;
}}
.empty {{ padding:18px; border:1px dashed var(--line); border-radius:12px; color:var(--muted); }}
.note {{ border-left:4px solid var(--warn); background:#171a28; padding:13px 15px; border-radius:10px; }}
code {{ color:#d9e8ff; }}
@media(max-width:900px) {{ .metrics {{ grid-template-columns:repeat(2,1fr); }} .gallery {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<main>
<header>
  <div>
    <span class="badge">HARPia · POC local</span>
    <h1>YOLO · detecção de pessoas em vídeo</h1>
    <div class="muted">Painel gerado a partir dos artefatos reais da execução.</div>
  </div>
  <div class="muted">Fonte: {source_link}</div>
</header>

<section class="metrics">{metrics_cards}</section>

<div class="note">
  O vídeo mantém {source_fps:.3f} FPS para reprodução, enquanto a máquina processou
  {processing_fps:.3f} FPS. A inferência ficou aproximadamente {realtime_ratio:.2f}×
  abaixo do tempo real neste hardware. Parâmetros: imgsz={params.get("imgsz")},
  conf={params.get("confidence_threshold")}, device={html.escape(str(params.get("device")))}.
</div>

<h2>Vídeo anotado</h2>
<section class="panel">{video_block}</section>

<h2>Evidências representativas</h2>
{evidence_gallery(metrics, report_path)}

<h2>Benchmark YOLO11n × YOLO11s</h2>
{comparison_table(comparison)}

<h2>Log da execução</h2>
<section class="panel">{log_block}</section>

<p class="muted">
Métricas: <code>{html.escape(str(DEFAULT_METRICS))}</code> ·
Relatório: <code>{html.escape(str(report_path))}</code>
</p>
</main>
</body>
</html>
"""


def main() -> int:
    args = build_parser().parse_args()
    if not args.metrics.is_file():
        raise SystemExit(f"ERRO: métricas não encontradas: {args.metrics}")

    metrics = load_json(args.metrics)
    source = load_json(args.source) if args.source.is_file() else {}
    comparison = read_comparison(args.comparison)

    video_path = args.video or Path(metrics.get("output_video", "output/yolo11n_people.mp4"))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    report = render_report(
        metrics=metrics,
        comparison=comparison,
        source=source,
        report_path=args.output,
        video_path=video_path,
        log_path=args.log,
        log_lines=args.log_lines,
    )
    args.output.write_text(report, encoding="utf-8")

    print(f"Painel salvo em: {args.output}")
    print(f"Vídeo associado: {video_path}")
    if args.log:
        print(f"Log associado: {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
