# ruff: noqa: I001
from __future__ import annotations

import re
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted,
    Table, TableStyle, ListFlowable, ListItem,
)

rl_config.invariant = True

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'docs' / 'report_sources'
OUT = ROOT / 'docs' / 'reports'
OUT.mkdir(parents=True, exist_ok=True)

NAVY = HexColor('#0B132B')
BLUE = HexColor('#2F80ED')
CYAN = HexColor('#56CCF2')
TEXT = HexColor('#1F2D3D')
MUTED = HexColor('#5F6F82')
MID = HexColor('#D9E2EF')
LIGHT = HexColor('#F5F8FC')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='RptTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=25, leading=30, textColor=NAVY, spaceAfter=12))
styles.add(ParagraphStyle(name='RptH1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=NAVY, spaceBefore=6, spaceAfter=8))
styles.add(ParagraphStyle(name='RptH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=BLUE, spaceBefore=8, spaceAfter=5))
styles.add(ParagraphStyle(name='RptBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.4, leading=14, textColor=TEXT, spaceAfter=6))
styles.add(ParagraphStyle(name='RptSmall', parent=styles['BodyText'], fontName='Helvetica', fontSize=8, leading=11, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle(name='RptQuote', parent=styles['BodyText'], fontName='Helvetica-Oblique', fontSize=9.2, leading=13.5, textColor=TEXT, backColor=LIGHT, borderColor=BLUE, borderWidth=1, borderPadding=7, leftIndent=8, rightIndent=8, spaceAfter=7))
code_style = ParagraphStyle(name='RptCode', fontName='Courier', fontSize=7.2, leading=9.3, textColor=NAVY, backColor=HexColor('#F2F6FB'), borderPadding=7, spaceBefore=4, spaceAfter=8)


def esc(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<u>\1</u> (\2)', text)
    return text


def on_page(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        w, h = A4
        canvas.setStrokeColor(MID)
        canvas.line(1.5*cm, h-1.0*cm, w-1.5*cm, h-1.0*cm)
        canvas.setFont('Helvetica-Bold', 7.5)
        canvas.setFillColor(NAVY)
        canvas.drawString(1.5*cm, h-0.72*cm, doc.title)
        canvas.setFont('Helvetica', 7.2)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w-1.5*cm, 0.62*cm, f'Pagina {doc.page}')
        canvas.line(1.5*cm, 0.92*cm, w-1.5*cm, 0.92*cm)
    canvas.restoreState()


def markdown_to_story(text: str):
    lines = text.splitlines()
    story = []
    i = 0
    in_code = False
    code_lines = []
    first_h1 = True
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                story.append(Preformatted('\n'.join(code_lines), code_style))
                in_code = False
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            story.append(Spacer(1, 0.08*cm))
            i += 1
            continue
        if line.startswith('# '):
            if not first_h1:
                story.append(PageBreak())
            story.append(Paragraph(inline(line[2:]), styles['RptTitle']))
            first_h1 = False
            i += 1
            continue
        if line.startswith('## '):
            story.append(Paragraph(inline(line[3:]), styles['RptH1']))
            i += 1
            continue
        if line.startswith('### '):
            story.append(Paragraph(inline(line[4:]), styles['RptH2']))
            i += 1
            continue
        if line.startswith('> '):
            story.append(Paragraph(inline(line[2:]), styles['RptQuote']))
            i += 1
            continue
        if line.startswith('|') and line.endswith('|'):
            table_lines = []
            while i < len(lines) and lines[i].startswith('|') and lines[i].endswith('|'):
                table_lines.append(lines[i])
                i += 1
            rows = []
            for j, tl in enumerate(table_lines):
                cells = [c.strip() for c in tl.strip('|').split('|')]
                if j == 1 and all(set(c) <= set('-: ') for c in cells):
                    continue
                rows.append([Paragraph(inline(c), styles['RptSmall'] if j == 0 else styles['RptBody']) for c in cells])
            if rows:
                col_count = len(rows[0])
                widths = [(16.1*cm)/col_count]*col_count
                t = Table(rows, colWidths=widths, repeatRows=1)
                ts = [('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.35,MID),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white)]
                t.setStyle(TableStyle(ts))
                story.append(t)
                story.append(Spacer(1, 0.15*cm))
            continue
        if re.match(r'^[-*] ', line):
            items = []
            while i < len(lines) and re.match(r'^[-*] ', lines[i]):
                items.append(ListItem(Paragraph(inline(lines[i][2:]), styles['RptBody']), leftIndent=12))
                i += 1
            story.append(ListFlowable(items, bulletType='bullet', leftIndent=18, bulletFontSize=6.5, bulletColor=BLUE, spaceAfter=5))
            continue
        if re.match(r'^\d+\. ', line):
            items = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                items.append(ListItem(Paragraph(inline(re.sub(r'^\d+\. ', '', lines[i])), styles['RptBody']), leftIndent=14))
                i += 1
            story.append(ListFlowable(items, bulletType='1', leftIndent=22, bulletFontName='Helvetica-Bold', bulletFontSize=8, bulletColor=BLUE, spaceAfter=5))
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#|>|```|[-*] |\d+\. |\|)', lines[i]):
            para.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(' '.join(para)), styles['RptBody']))
    return story


def build(source_name: str, output_name: str, title: str):
    source = SRC / source_name
    output = OUT / output_name
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.45*cm, bottomMargin=1.3*cm, title=title, author='Projeto HARPia')
    doc.build(markdown_to_story(source.read_text(encoding='utf-8')), onFirstPage=on_page, onLaterPages=on_page)
    print(output)


if __name__ == '__main__':
    build('technical_report.md', 'Relatorio_Tecnico_HARPia_YOLO_POC.pdf', 'HARPia - Relatorio Tecnico YOLO POC')
    build('code_guide.md', 'Guia_Estudo_Codigo_HARPia_YOLO.pdf', 'HARPia - Guia de Estudo do Codigo YOLO')
