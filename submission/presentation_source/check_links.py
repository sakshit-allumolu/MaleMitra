#!/usr/bin/env python3
"""QA helper: checks relative Markdown links and extracts Mermaid blocks from docs/ and submission/."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
files = [p for d in ("docs", "submission") for p in (ROOT / d).rglob("*.md")]
bad = 0
for f in files:
    txt = f.read_text()
    for m in re.finditer(r"\]\(([^)\s]+)\)", txt):
        t = m.group(1)
        if t.startswith(("http", "mailto:", "#")):
            continue
        path = t.split("#")[0]
        if path and not (f.parent / path).resolve().exists():
            print("BROKEN", f.relative_to(ROOT), "->", t)
            bad += 1
    anchors = {a for a in re.findall(r"\]\(([^)\s]*#[^)\s]+)\)", txt)}
print("files:", len(files), "broken links:", bad)
sys.exit(1 if bad else 0)
