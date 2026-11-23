#!/usr/bin/env python3
"""Create and read Google-Docs-friendly .docx files (notes, exercises, prompts).

Zero external dependencies (Python 3 stdlib only).
Converts Markdown input (from stdin or --input) directly into formatted .docx
without keeping .md files around. Any <details>/<summary> Answer Key block is
rendered in invisible white text on a separate page for agent-assisted grading.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

ROOT_DIR = Path(__file__).resolve().parent.parent
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOC_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:color w:val="222222"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="120" w:after="180"/>
      <w:pBdr>
        <w:bottom w:val="single" w:sz="8" w:space="6" w:color="1F4E79"/>
      </w:pBdr>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="1F4E79"/>
      <w:sz w:val="34"/>
      <w:szCs w:val="34"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="260" w:after="100"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="2E75B6"/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="180" w:after="80"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="333333"/>
      <w:sz w:val="23"/>
      <w:szCs w:val="23"/>
    </w:rPr>
  </w:style>
</w:styles>
"""

INLINE_TOKEN_RE = re.compile(
    r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))"
)


def make_run(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    color: str | None = None,
    hidden_white: bool = False,
) -> str:
    if not text:
        return ""
    rpr_parts: list[str] = []
    if bold:
        rpr_parts.append("<w:b/>")
    if italic:
        rpr_parts.append("<w:i/>")
    if hidden_white:
        rpr_parts.append('<w:color w:val="FFFFFF"/>')
        rpr_parts.append('<w:sz w:val="16"/>')
        rpr_parts.append('<w:szCs w:val="16"/>')
    elif code:
        rpr_parts.append('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>')
        rpr_parts.append('<w:color w:val="1B4F72"/>')
        rpr_parts.append('<w:shd w:val="clear" w:color="auto" w:fill="EEF4FA"/>')
    elif color:
        rpr_parts.append(f'<w:color w:val="{color}"/>')

    rpr = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""
    safe = escape(text)
    return f'<w:r>{rpr}<w:t xml:space="preserve">{safe}</w:t></w:r>'


def inline_md_to_runs(
    text: str,
    *,
    base_bold: bool = False,
    base_italic: bool = False,
    hidden_white: bool = False,
) -> str:
    """Convert inline markdown (**bold**, *italic*, `code`, [label](url)) to OOXML runs."""
    runs: list[str] = []
    pos = 0
    for match in INLINE_TOKEN_RE.finditer(text):
        if match.start() > pos:
            runs.append(
                make_run(
                    text[pos : match.start()],
                    bold=base_bold,
                    italic=base_italic,
                    hidden_white=hidden_white,
                )
            )
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            runs.append(
                inline_md_to_runs(
                    token[2:-2],
                    base_bold=True,
                    base_italic=base_italic,
                    hidden_white=hidden_white,
                )
            )
        elif token.startswith("*") and token.endswith("*"):
            runs.append(
                inline_md_to_runs(
                    token[1:-1],
                    base_bold=base_bold,
                    base_italic=True,
                    hidden_white=hidden_white,
                )
            )
        elif token.startswith("`") and token.endswith("`"):
            runs.append(
                make_run(
                    token[1:-1],
                    bold=base_bold,
                    italic=base_italic,
                    code=not hidden_white,
                    hidden_white=hidden_white,
                )
            )
        elif token.startswith("[") and "](" in token:
            label = token[1 : token.index("](")]
            runs.append(
                make_run(
                    label,
                    bold=base_bold,
                    italic=base_italic,
                    hidden_white=hidden_white,
                )
            )
        pos = match.end()
    if pos < len(text):
        runs.append(
            make_run(
                text[pos:],
                bold=base_bold,
                italic=base_italic,
                hidden_white=hidden_white,
            )
        )
    return "".join(runs)


def make_paragraph(
    runs_xml: str,
    *,
    style: str | None = None,
    indent_left: int = 0,
    space_before: int | None = None,
    space_after: int | None = None,
    page_break_before: bool = False,
    bottom_border: bool = False,
    left_accent: bool = False,
) -> str:
    ppr_parts: list[str] = []
    if style:
        ppr_parts.append(f'<w:pStyle w:val="{style}"/>')
    if page_break_before:
        ppr_parts.append("<w:pageBreakBefore/>")
    if indent_left:
        ppr_parts.append(f'<w:ind w:left="{indent_left}"/>')
    if space_before is not None or space_after is not None:
        attrs = []
        if space_before is not None:
            attrs.append(f'w:before="{space_before}"')
        if space_after is not None:
            attrs.append(f'w:after="{space_after}"')
        ppr_parts.append(f"<w:spacing {' '.join(attrs)}/>")
    if bottom_border:
        ppr_parts.append(
            '<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="4" w:color="CCCCCC"/></w:pBdr>'
        )
    if left_accent:
        ppr_parts.append(
            '<w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="2E75B6"/></w:pBdr>'
        )
        ppr_parts.append('<w:shd w:val="clear" w:color="auto" w:fill="F4F8FC"/>')
    ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>" if ppr_parts else ""
    return f"<w:p>{ppr}{runs_xml}</w:p>"


def make_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    num_cols = max(len(r) for r in rows)
    col_width = max(1400, 9360 // max(1, num_cols))

    grid_xml = "".join(f'<w:gridCol w:w="{col_width}"/>' for _ in range(num_cols))
    tbl_pr = (
        "<w:tblPr>"
        '<w:tblW w:w="9360" w:type="dxa"/>'
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="DDDDDD"/>'
        "</w:tblBorders>"
        "<w:tblCellMar>"
        '<w:top w:w="80" w:type="dxa"/>'
        '<w:left w:w="120" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/>'
        '<w:right w:w="120" w:type="dxa"/>'
        "</w:tblCellMar>"
        "</w:tblPr>"
    )

    tr_xml_list: list[str] = []
    for r_idx, row in enumerate(rows):
        is_header = r_idx == 0
        cells_xml: list[str] = []
        for c_idx in range(num_cols):
            cell_text = row[c_idx] if c_idx < len(row) else ""
            shd = '<w:shd w:val="clear" w:color="auto" w:fill="E8F0FE"/>' if is_header else ""
            tc_pr = f'<w:tcPr><w:tcW w:w="{col_width}" w:type="dxa"/>{shd}</w:tcPr>'
            runs = inline_md_to_runs(cell_text, base_bold=is_header)
            para = make_paragraph(runs, space_before=0, space_after=40)
            cells_xml.append(f"<w:tc>{tc_pr}{para}</w:tc>")
        tr_pr = "<w:trPr><w:tblHeader/></w:trPr>" if is_header else ""
        tr_xml_list.append(f"<w:tr>{tr_pr}{''.join(cells_xml)}</w:tr>")

    return f"<w:tbl>{tbl_pr}<w:tblGrid>{grid_xml}</w:tblGrid>{''.join(tr_xml_list)}</w:tbl>"


def is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|").strip()
    if not stripped:
        return False
    parts = [p.strip() for p in stripped.split("|")]
    return all(bool(re.fullmatch(r":?-{3,}:?", p)) for p in parts)


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [c.strip() for c in stripped.split("|")]


def markdown_to_document_xml(md_text: str) -> str:
    lines = md_text.splitlines()
    blocks: list[str] = []
    i = 0
    in_answer_key = False

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        # Handle <details> / <summary> -> render Answer Key in invisible white text on a new page
        if stripped.startswith("<details"):
            in_answer_key = True
            i += 1
            continue
        if stripped == "</details>":
            in_answer_key = False
            i += 1
            continue
        if stripped.startswith("<summary"):
            in_answer_key = True
            clean_title = re.sub(r"<[^>]+>", "", stripped).strip()
            clean_title = re.sub(r"\s*\(click to reveal\)\s*", "", clean_title, flags=re.IGNORECASE)
            blocks.append(
                make_paragraph(
                    inline_md_to_runs(clean_title or "Answer Key", base_bold=True, hidden_white=True),
                    page_break_before=True,
                    space_before=0,
                    space_after=60,
                )
            )
            i += 1
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}", stripped):
            if not in_answer_key:
                blocks.append(make_paragraph("", space_before=60, space_after=120, bottom_border=True))
            i += 1
            continue

        # Blockquote (e.g., "> Tip: ...")
        if stripped.startswith(">") and not in_answer_key:
            quote_text = stripped.lstrip(">").strip()
            blocks.append(
                make_paragraph(
                    inline_md_to_runs(quote_text),
                    indent_left=320,
                    space_before=60,
                    space_after=100,
                    left_accent=True,
                )
            )
            i += 1
            continue

        # Headings (H1–H4)
        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            level = min(3, len(heading_match.group(1)))
            content = heading_match.group(2).strip()
            if in_answer_key:
                blocks.append(
                    make_paragraph(
                        inline_md_to_runs(content, base_bold=True, hidden_white=True),
                        space_before=80,
                        space_after=40,
                    )
                )
            else:
                blocks.append(
                    make_paragraph(
                        inline_md_to_runs(content),
                        style=f"Heading{level}",
                    )
                )
            i += 1
            continue

        # Tables
        if stripped.startswith("|") and i + 1 < len(lines) and is_table_separator(lines[i + 1]):
            table_rows = [split_table_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_rows.append(split_table_row(lines[i]))
                i += 1
            blocks.append(make_table(table_rows))
            blocks.append(make_paragraph("", space_before=0, space_after=80))
            continue

        # Numbered list item
        num_match = re.match(r"^(\d+\.)\s+(.*)$", stripped)
        if num_match:
            num_label = num_match.group(1)
            item_text = num_match.group(2)
            runs = make_run(
                f"{num_label} ", bold=True, hidden_white=in_answer_key
            ) + inline_md_to_runs(item_text, hidden_white=in_answer_key)
            blocks.append(
                make_paragraph(
                    runs,
                    indent_left=320,
                    space_before=20 if in_answer_key else 40,
                    space_after=40 if in_answer_key else 100,
                )
            )
            i += 1
            while i < len(lines) and lines[i].startswith("   ") and lines[i].strip():
                cont = lines[i].strip()
                sub_bullet = re.match(r"^[-*]\s+(.*)$", cont)
                if sub_bullet:
                    cont_runs = make_run(
                        "◦  ",
                        bold=True,
                        color=None if in_answer_key else "2E75B6",
                        hidden_white=in_answer_key,
                    ) + inline_md_to_runs(sub_bullet.group(1), hidden_white=in_answer_key)
                else:
                    cont_runs = inline_md_to_runs(cont, hidden_white=in_answer_key)
                blocks.append(
                    make_paragraph(
                        cont_runs,
                        indent_left=640,
                        space_before=0,
                        space_after=40 if in_answer_key else 100,
                    )
                )
                i += 1
            continue

        # Bullet list item (including nested indented bullets)
        bullet_match = re.match(r"^(\s*)[-*]\s+(.*)$", raw)
        if bullet_match:
            indent_spaces = len(bullet_match.group(1))
            is_sub = indent_spaces >= 2
            bullet_char = "◦  " if is_sub else "•  "
            indent_val = 640 if is_sub else 360
            runs = make_run(
                bullet_char,
                bold=True,
                color=None if in_answer_key else "2E75B6",
                hidden_white=in_answer_key,
            ) + inline_md_to_runs(bullet_match.group(2).strip(), hidden_white=in_answer_key)
            blocks.append(
                make_paragraph(
                    runs,
                    indent_left=indent_val,
                    space_before=20,
                    space_after=40 if in_answer_key else 80,
                )
            )
            i += 1
            continue

        # Regular paragraph
        blocks.append(
            make_paragraph(
                inline_md_to_runs(stripped, hidden_white=in_answer_key),
                space_after=40 if in_answer_key else None,
            )
        )
        i += 1

    body = "\n".join(blocks)
    sect_pr = (
        "<w:sectPr>"
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        f"  <w:body>\n{body}\n{sect_pr}\n  </w:body>\n"
        "</w:document>\n"
    )


def write_docx_from_md_text(md_text: str, out_path: Path) -> Path:
    doc_xml = markdown_to_document_xml(md_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS_XML)
        zf.writestr("word/styles.xml", STYLES_XML)
        zf.writestr("word/document.xml", doc_xml)
    return out_path


def read_docx(docx_path: Path) -> str:
    """Extract readable plain text (paragraphs and tables) from a .docx file."""
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(f"{{{W_NS}}}body")
    if body is None:
        return ""

    out_lines: list[str] = []
    for child in body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            texts = [t.text or "" for t in child.iter(f"{{{W_NS}}}t")]
            line = "".join(texts).strip()
            if line:
                out_lines.append(line)
        elif tag == "tbl":
            for tr in child.findall(f"{{{W_NS}}}tr"):
                cells = []
                for tc in tr.findall(f"{{{W_NS}}}tc"):
                    cell_txt = "".join(t.text or "" for t in tc.iter(f"{{{W_NS}}}t")).strip()
                    cells.append(cell_txt)
                out_lines.append(" | ".join(cells))
            out_lines.append("")
    return "\n".join(out_lines)


def cmd_write(args: argparse.Namespace) -> int:
    if args.input:
        md_text = Path(args.input).read_text(encoding="utf-8")
    else:
        md_text = sys.stdin.read()

    if not md_text.strip():
        print("Error: empty input.", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    write_docx_from_md_text(md_text, out_path)
    rel = out_path.relative_to(ROOT_DIR) if out_path.is_relative_to(ROOT_DIR) else out_path
    print(f"Wrote {rel}")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        return 1
    print(read_docx(path))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write Google-Docs-friendly .docx files from Markdown text and read them back."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write", help="Write a .docx file from stdin or --input Markdown.")
    p_write.add_argument("output", help="Destination .docx file path")
    p_write.add_argument("--input", "-i", help="Optional Markdown input file (defaults to stdin)")
    p_write.set_defaults(func=cmd_write)

    p_read = sub.add_parser("read", help="Extract text from a .docx file for reading/review.")
    p_read.add_argument("file", help="Path to .docx file")
    p_read.set_defaults(func=cmd_read)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
