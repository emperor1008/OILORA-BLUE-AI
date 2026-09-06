"""Extract text content from the five Oilora Blue AI project .docx documents.

Stdlib-only (zipfile + ElementTree), no third-party packages required.
Writes one .txt file per document into the same directory.
"""
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

DOCS = {
    "01_PRD": r"C:\Users\BINIT\OneDrive\Documents\01_SamudraTrace_AI_PRD.docx",
    "02_Technical_Architecture": r"C:\Users\BINIT\OneDrive\Documents\02_SamudraTrace_AI_Technical_Architecture.docx",
    "03_Security_and_Access": r"C:\Users\BINIT\OneDrive\Documents\03_SamudraTrace_AI_Security_and_Access.docx",
    "04_Frontend_Specification": r"C:\Users\BINIT\OneDrive\Documents\04_SamudraTrace_AI_Frontend_Specification.docx",
    "05_Feature_Ticket_List": r"C:\Users\BINIT\OneDrive\Documents\05_SamudraTrace_AI_Feature_Ticket_List.docx",
}

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_text(docx_path: str) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(docx_path) as zf:
        with zf.open("word/document.xml") as fh:
            tree = ET.parse(fh)
    root = tree.getroot()
    body = root.find(f"{W_NS}body")
    if body is None:
        return ""
    for elem in body.iter():
        tag = elem.tag
        if tag == f"{W_NS}p":
            # Paragraph: collect its w:t text runs
            parts: list[str] = []
            for t in elem.iter(f"{W_NS}t"):
                parts.append(t.text or "")
            # Preserve w:tab characters
            for tab in elem.iter(f"{W_NS}tab"):
                parts.append("\t")
            line = "".join(parts)
            lines.append(line)
        elif tag == f"{W_NS}tbl":
            # Table: handled by iterating rows/cells below; ensure blank line separation
            lines.append("[TABLE]")
    # Tables need proper row/cell extraction; do a second pass for tables
    text = "\n".join(lines)
    return text


def extract_tables(docx_path: str) -> str:
    """Extract tables row-by-row with cell boundaries."""
    out: list[str] = []
    with zipfile.ZipFile(docx_path) as zf:
        with zf.open("word/document.xml") as fh:
            tree = ET.parse(fh)
    root = tree.getroot()
    body = root.find(f"{W_NS}body")
    if body is None:
        return ""
    for tbl in body.iter(f"{W_NS}tbl"):
        for tr in tbl.iter(f"{W_NS}tr"):
            cells: list[str] = []
            for tc in tr.iter(f"{W_NS}tc"):
                cell_text: list[str] = []
                for p in tc.iter(f"{W_NS}p"):
                    parts: list[str] = []
                    for t in p.iter(f"{W_NS}t"):
                        parts.append(t.text or "")
                    cell_text.append("".join(parts))
                cells.append(" | ".join(ct for ct in cell_text if ct.strip()))
            if cells:
                out.append(" || ".join(cells))
        out.append("")
    return "\n".join(out)


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    for name, path in DOCS.items():
        if not os.path.exists(path):
            print(f"MISSING: {name}: {path}")
            continue
        body_text = extract_text(path)
        table_text = extract_tables(path)
        combined = (
            f"===== {name} (source: {os.path.basename(path)}) =====\n\n"
            + body_text
            + "\n\n===== TABLE CONTENT =====\n"
            + table_text
        )
        out_path = os.path.join(out_dir, f"{name}.txt")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(combined)
        words = len(combined.split())
        print(f"OK {name}: {words} words -> {out_path}")


if __name__ == "__main__":
    main()