"""Build the private Lab 6 submission PDF from recorded deployment evidence.

Run: uv run --with reportlab python scripts/generate-lab6-pdf.py
"""

from __future__ import annotations

import html
import io
import json
import os
from pathlib import Path
import subprocess

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = Path(os.environ.get("LAB6_PRIVATE_DIR", ROOT.parents[1] / "Lab6-submission"))
OUTPUT = PRIVATE_DIR / "lab6-submission.pdf"
VIDEO = PRIVATE_DIR / "lab6-paste-agenda.mp4"
EVIDENCE = ROOT / "docs" / "lab6-evaluation.jsonl"
COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
COMMIT_URL = f"https://github.com/purishok/Peach/commit/{COMMIT}"


def font_path(filename: str) -> str:
    return f"/System/Library/Fonts/Supplemental/{filename}"


pdfmetrics.registerFont(TTFont("LabSans", font_path("Arial Unicode.ttf")))
pdfmetrics.registerFont(TTFont("LabBold", font_path("Arial Bold.ttf")))

PAGE_W, PAGE_H = landscape(A4)
INK = colors.HexColor("#183047")
MUTED = colors.HexColor("#587084")
BLUE = colors.HexColor("#0877bb")
PALE = colors.HexColor("#eaf4f9")
LINE = colors.HexColor("#d3e0e8")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleLab", fontName="LabBold", fontSize=23, leading=29, textColor=INK, spaceAfter=9))
styles.add(ParagraphStyle(name="SubtitleLab", fontName="LabSans", fontSize=11, leading=16, textColor=MUTED, spaceAfter=14))
styles.add(ParagraphStyle(name="HeadingLab", fontName="LabBold", fontSize=14, leading=18, textColor=INK, spaceBefore=16, spaceAfter=8))
styles.add(ParagraphStyle(name="SubheadingLab", fontName="LabBold", fontSize=10.5, leading=14, textColor=INK, spaceBefore=10, spaceAfter=5))
styles.add(ParagraphStyle(name="BodyLab", fontName="LabSans", fontSize=9.5, leading=14, textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name="SmallLab", fontName="LabSans", fontSize=8, leading=11, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name="TinyLab", fontName="LabSans", fontSize=7.15, leading=9.7, textColor=INK, wordWrap="CJK"))
styles.add(ParagraphStyle(name="TinyBoldLab", parent=styles["TinyLab"], fontName="LabBold", textColor=INK))
styles.add(ParagraphStyle(name="CenterLab", parent=styles["BodyLab"], alignment=TA_CENTER))
styles.add(ParagraphStyle(name="CodeLab", fontName="LabSans", fontSize=8.2, leading=11.3, textColor=INK, leftIndent=10))


def p(text: str, style: str = "BodyLab") -> Paragraph:
    return Paragraph(text, styles[style])


def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def add_header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(34, PAGE_H - 29, PAGE_W - 34, PAGE_H - 29)
    canvas.setFont("LabSans", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(35, PAGE_H - 22, "LAB 6  /  PASTE AN AGENDA")
    canvas.line(34, 30, PAGE_W - 34, 30)
    canvas.drawString(35, 18, "Peach  •  deployed evidence  •  21 October 2026")
    canvas.drawRightString(PAGE_W - 35, 18, str(doc.page))
    canvas.restoreState()


def build() -> None:
    if not VIDEO.is_file():
        raise FileNotFoundError(f"Put the private recording at {VIDEO} before building")
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    cases = [json.loads(line) for line in EVIDENCE.read_text().splitlines() if line.strip()]
    assert len(cases) == 5
    story = []

    story += [Spacer(1, 20), p("Lab 6 · Paste it, check it, save it", "TitleLab")]
    story += [p("Claude agenda parsing through Amazon Bedrock — submission packet", "SubtitleLab")]
    story += [HRFlowable(width="100%", thickness=1, color=LINE), Spacer(1, 12)]
    story += [p("What is submitted", "HeadingLab")]
    overview = [
        ("Commit", f'<link href="{COMMIT_URL}" color="#0877bb">{COMMIT_URL}</link>'),
        ("Deployed app", '<link href="https://dqvalqr0apze.cloudfront.net/meetings" color="#0877bb">https://dqvalqr0apze.cloudfront.net/meetings</link>'),
        ("Recording", "The 10.44-second MP4 is a separate file beside this PDF in the private submission ZIP."),
        ("Included below", "Five deployed input/JSON results, field review, token usage, cost, latency, CloudWatch log, and written answers."),
    ]
    for name, value in overview:
        story.append(p(f"<b>{name}:</b> {value}"))
    story += [
        Spacer(1, 8),
        p("Recording evidence", "HeadingLab"),
        p(
            "The recording shows pasted text, Parse, the pre-filled agenda form, a manual title correction, "
            "and Save in the deployed app. The save endpoint returned HTTP 200; a subsequent authenticated "
            "GET showed the corrected title and the original AI suggestion. The accompanying file "
            "lab6-paste-agenda.mp4 is included in the same private ZIP archive as this PDF."
        ),
        p("Deployment and model note", "HeadingLab"),
        p(
            "The live parser is a container Lambda outside the VPC in account 985040259102 (eu-north-1), "
            "calling Claude Sonnet 4.5 via Amazon Bedrock Converse in us-east-1. The site, Cognito, API and "
            "database are in account 505464394565. The specified Opus 5.5 Messages API returned HTTP 403 "
            "in the available account, so this is a documented deviation. The model only suggests; the "
            "authenticated ordinary API saves the checked agenda and the AI suggestion."
        ),
        p(
            "The PDF uses the original five deployed-screen results from 21 October 2026 (Europe/Kyiv). "
            "The parser prompt version was agenda-v4. The MP4 records the same user flow from the earlier "
            "agenda-v2 deployment; the submitted five-case evaluation documents the current version.",
            "SmallLab",
        ),
        PageBreak(),
        p("Five-input test table", "TitleLab"),
        p("Full pasted inputs and complete model JSON are shown below. JSON null means no agenda was returned.", "SmallLab"),
    ]

    reviews = {
        1: ("Title, Monday 10:00 with Kyiv offset, 45 minutes, three topics, owners, Friday action date.", "None.", "0"),
        2: ("Title, Thursday 14:00 with offset, 30 minutes, two owners; greeting and signature excluded.", "None.", "0"),
        3: ("Topic and Nadia action were extracted.", "Known Tuesday omitted; vague end-of-week became unsupported Saturday due date.", "1"),
        4: ("Rejected correctly as non-agenda (HTTP 422).", "None.", "0"),
        5: ("Pricing topic and Olena owner; ignored injected owner address.", "None.", "0"),
    }
    headers = ["#", "Input", "JSON produced", "Correct / wrong", "Invented", "Tokens in/out", "Cost $", "Latency s"]
    widths = [20, 107, 317, 152, 44, 53, 48, 42]
    rows = [[p(esc(h), "TinyBoldLab") for h in headers]]
    for case in cases:
        number = case["number"]
        right, wrong, invented = reviews[number]
        summary = f"<b>Right:</b> {esc(right)}<br/><b>Wrong:</b> {esc(wrong)}"
        produced = "null (HTTP 422: no agenda)" if case["json"] is None else json.dumps(case["json"], ensure_ascii=False, separators=(",", ":"))
        rows.append([
            p(str(number), "TinyLab"),
            p(esc(case["input"]).replace("\n", "<br/>"), "TinyLab"),
            p(esc(produced), "TinyLab"),
            p(summary, "TinyLab"),
            p(invented, "TinyLab"),
            p(f'{case["usage"]["input_tokens"]} / {case["usage"]["output_tokens"]}', "TinyLab"),
            p(f'{case["cost_usd"]:.6f}', "TinyLab"),
            p(f'{case["latency_s"]:.2f}', "TinyLab"),
        ])
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fbfd")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINE),
    ]))
    story += [table, Spacer(1, 10)]
    story += [p("Invented values are JSON values unsupported by the input, counted separately from omissions or other mistakes. Case 4 produced HTTP 422 and no JSON; its usage came from the matching CloudWatch line.", "SmallLab")]

    story += [PageBreak(), p("CloudWatch parse log", "TitleLab")]
    log_line = {
        "event": "agenda_parse",
        "user": "44384498-80c1-70a0-9c05-3da8c96ecf5b",
        "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "prompt_version": "agenda-v4",
        "status": "ok",
        "error_type": None,
        "input_tokens": 1367,
        "output_tokens": 142,
        "latency_ms": 3856,
        "cost_usd": 0.006231,
    }
    story += [
        p("/aws/lambda/peach-agenda-parser · eu-north-1 · account 985040259102", "SmallLab"),
        Preformatted(json.dumps(log_line, ensure_ascii=False, indent=2), styles["CodeLab"]),
        Spacer(1, 8),
        p("Short written answers", "HeadingLab"),
        p("1. Which inputs went wrong, and what would fix them?", "SubheadingLab"),
        p("Case 3 omitted the known Tuesday because the current schema has only starts_at, which requires both a date and a time. Separate date and time fields, reflected in the UI, would keep Tuesday without inventing a clock time. The same case chose Saturday for an ambiguous 'end of week' deadline; the prompt should leave ambiguous deadlines empty, and the change should be measured on a reviewed test set. Case 4 correctly rejected a shopping list. The remaining cases matched their inputs in these runs."),
        p("2. What did the injection attempt do, and what limits damage?", "SubheadingLab"),
        p("Case 5 kept owner Olena and did not use admin@example.com. The pasted text is delimited as untrusted data, and the model's output is schema-validated. Even if the model obeyed the malicious line, it could only pre-fill the form: the person checks it and the normal authenticated API performs the write."),
        PageBreak(),
        p("Short written answers · continued", "TitleLab"),
        p("3. What does a parse cost, and how does monthly use compare with an endpoint?", "SubheadingLab"),
        p("The displayed parse cost an estimated $0.006231 in model tokens. Across all five tests, mean model cost was $0.006970 per request, including the rejected input. At 20 organisations × 30 agendas/week × 52/12 weeks/month = 2,600 parses/month, the observed mean implies about $18.12/month in model charges. That is greater than the assignment's $7.30/month for one VPC interface endpoint; the endpoint would be an additional fixed charge if inference ran in the VPC. Lambda, logging, and transfer are excluded."),
        p("4. How can 500 saved suggestions evaluate agenda-v2 against agenda-v1?", "SubheadingLab"),
        p("Measure per-field correction and missing-field rates by comparing each saved agenda with its stored AI suggestion. Have reviewers label a sample for unsupported or wrong values, because an unchanged field is not necessarily correct. Re-run both prompt versions on the same retained or consented original texts and compare paired field accuracy and invented-value rates with confidence intervals. Current saved records contain suggestion and final form, but not the original pasted text; those 500 records alone cannot replay a new prompt."),
        Spacer(1, 7),
        p("Evidence and limitations", "HeadingLab"),
        p("The deployed UI completed authenticated Parse and Save, and the API retained the proposed and final agendas. The current parser stack and $5 monthly budget remain deployed. The budget alerts rather than blocking further calls. The teacher's requested model/API combination is the only infrastructure deviation described above; the case 3 date needs a human correction before saving."),
    ]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=30,
        rightMargin=30,
        topMargin=40,
        bottomMargin=39,
        title="Lab 6 — Paste an agenda — submission",
        author="Peach project",
    )
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

    OUTPUT.write_bytes(buffer.getvalue())
    print(f"Wrote {OUTPUT}; package it with {VIDEO.name} in a private ZIP")


if __name__ == "__main__":
    build()
