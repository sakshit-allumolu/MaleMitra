#!/usr/bin/env python3
"""Builds the single .zip for the TechGig upload form (allowed: zip or ppt, max 100 MB).

One folder per Phase 1 deliverable:
  01_Problem_Statement_and_Solution/
  02_Working_Solution_Built_with_IBM_Bob/
  03_Source_Code_Repository/
  04_Presentation_Deck/
  05_Video_Demonstration/

Run from the repository root:
    /tmp/pptx_env/bin/python submission/build_submission_zip.py
        final build: refuses while placeholders or secrets remain
    /tmp/pptx_env/bin/python submission/build_submission_zip.py --allow-placeholders
        draft build only, do not upload

python-pptx is only used to check the deck for leftover placeholder boxes.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "MaleMitra_IBM_Bobathon_Submission"
OUT = ROOT / "submission" / f"{NAME}.zip"
LIMIT = 100 * 1024 * 1024

D1 = "01_Problem_Statement_and_Solution"
D2 = "02_Working_Solution_Built_with_IBM_Bob"
D3 = "03_Source_Code_Repository"
D4 = "04_Presentation_Deck"
D5 = "05_Video_Demonstration"

COPIES = [  # (source relative to repo root, destination inside the zip folder)
    ("docs/02_PROBLEM_STATEMENT_AND_SOLUTION.md", f"{D1}/Problem_Statement_and_Solution.md"),
    ("submission/EXECUTIVE_SUMMARY.md", f"{D1}/Executive_Summary.md"),
    ("docs/04_IBM_TECHNOLOGY_AND_AGENTIC_AI.md", f"{D2}/IBM_Bob_and_watsonx_Orchestrate.md"),
    ("docs/05_FEATURES_AND_USER_FLOWS.md", f"{D2}/Features_and_User_Flows.md"),
    ("docs/06_SETUP_AND_INSTALLATION.md", f"{D2}/How_to_Run_It.md"),
    ("docs/08_TESTING_AND_VALIDATION.md", f"{D2}/Testing_Results.md"),
    ("docs/10_IMPACT_AND_SCALABILITY.md", f"{D2}/Impact.md"),
    ("docs/09_SECURITY_PRIVACY_AND_RESPONSIBLE_AI.md", f"{D2}/Privacy_and_Human_Review.md"),
    ("docs/03_TECHNICAL_ARCHITECTURE.md", f"{D3}/Technical_Architecture.md"),
    ("docs/12_REPOSITORY_AND_LICENSE.md", f"{D3}/Repository_and_License.md"),
    ("submission/IBM_Bobathon_Presentation.pptx", f"{D4}/IBM_Bobathon_Presentation.pptx"),
    ("docs/15_VIDEO_DEMO_SCRIPT.md", f"{D5}/Video_Script.md"),
    ("submission/demo/VIDEO_LINK.txt", f"{D5}/VIDEO_LINK.txt"),
]
TREES = [
    ("submission/assets/screenshots", f"{D2}/screenshots"),
    ("submission/assets/diagrams", f"{D3}/diagrams"),
]

README = """# MaleMitra (ಮಳೆ ಮಿತ್ರ) — IBM Bobathon: Build for Bengaluru 2026

Theme: Smarter Streets, Better Living

| Phase 1 deliverable | Folder |
|---|---|
| 1. Problem statement and detailed solution description | `01_Problem_Statement_and_Solution/` |
| 2. A working solution built with IBM Bob | `02_Working_Solution_Built_with_IBM_Bob/` (how to run it, Bob and watsonx Orchestrate, tests, screenshots) |
| 3. Source code repository | `03_Source_Code_Repository/` (full code) and https://github.com/sakshit-allumolu/MaleMitra (branch `feature-demo`) |
| 4. Presentation deck | `04_Presentation_Deck/IBM_Bobathon_Presentation.pptx` |
| 5. Video demonstration | `05_Video_Demonstration/VIDEO_LINK.txt` |

Quick run (details in `02_Working_Solution_Built_with_IBM_Bob/How_to_Run_It.md`):

```bash
cd 03_Source_Code_Repository
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest backend/tests          # 242 passed on 15 Nov 2026
```
"""


def git_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def main():
    allow = "--allow-placeholders" in sys.argv
    stage_root = Path(tempfile.mkdtemp())
    stage = stage_root / NAME
    stage.mkdir()

    # 03: tracked files only, so .env, databases and node_modules can never be included
    for rel in git_files():
        src = ROOT / rel
        if src.is_file():
            dst = stage / D3 / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for rel, dest in COPIES:
        dst = stage / dest
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    for rel, dest in TREES:
        shutil.copytree(ROOT / rel, stage / dest, ignore=shutil.ignore_patterns(".DS_Store"))
    (stage / "README.md").write_text(README)

    # In the five deliverable folders, a link to a file that is not in the zip becomes plain text.
    link = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
    for d in (D1, D2, D4, D5):
        for md in (stage / d).rglob("*.md"):
            text = md.read_text()

            def repl(m):
                t = m.group(2)
                if t.startswith(("http", "mailto:", "#")):
                    return m.group(0)
                p = t.split("#")[0]
                return m.group(0) if (not p or (md.parent / p).resolve().exists()) else m.group(1)

            new = link.sub(repl, text)
            if new != text:
                md.write_text(new)
    for md in (stage / D3).glob("*.md"):
        if md.name in ("Technical_Architecture.md", "Repository_and_License.md"):
            text = md.read_text()
            new = link.sub(lambda m: m.group(0) if m.group(2).startswith(("http", "mailto:", "#")) or (md.parent / m.group(2).split("#")[0]).exists() else m.group(1), text)
            if new != text:
                md.write_text(new)

    # safety checks
    secrets = []
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip("\"'")
                if len(v) >= 12 and any(w in k.upper() for w in ("KEY", "SECRET", "TOKEN", "PASS")):
                    secrets.append(v)
    leaks, placeholders = [], []
    for f in stage.rglob("*"):
        if not f.is_file():
            continue
        try:
            t = f.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        rel = f.relative_to(stage).as_posix()
        if any(s in t for s in secrets):
            leaks.append(rel)
        in_code = rel.startswith((D3 + "/backend", D3 + "/frontend", D3 + "/orchestrate", D3 + "/scripts"))
        if "TEAM INPUT REQUIRED" in t and not in_code:
            placeholders.append(rel)
    try:
        from pptx import Presentation
        prs = Presentation(str(stage / D4 / "IBM_Bobathon_Presentation.pptx"))
        for i, s in enumerate(prs.slides, 1):
            blob = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            if "TEAM INPUT REQUIRED" in blob or "PLACEHOLDER:" in blob:
                placeholders.append(f"{D4}/ deck slide {i}")
    except ImportError:
        print("python-pptx not installed: deck placeholders not checked")

    if leaks:
        sys.exit("Refusing to build: secret value found in " + ", ".join(leaks))
    if placeholders and not allow:
        print("Unfilled placeholders in:\n  " + "\n  ".join(sorted(set(placeholders))))
        sys.exit("Refusing to build. Fill them, or add --allow-placeholders for a DRAFT zip.")

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(stage_root).as_posix())
    size = OUT.stat().st_size
    print(f"built {OUT.relative_to(ROOT)}  {size/1024/1024:.2f} MB (limit 100 MB)")
    if placeholders:
        print("DRAFT: placeholders remain in", len(set(placeholders)), "places. Do not upload this version.")
    shutil.rmtree(stage_root)
    if size > LIMIT:
        sys.exit("Zip exceeds 100 MB")


if __name__ == "__main__":
    main()
