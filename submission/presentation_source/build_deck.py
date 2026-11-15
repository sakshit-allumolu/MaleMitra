"""Builds submission/IBM_Bobathon_Presentation.pptx.

Run from the repository root:
    python3 -m venv /tmp/pptx_env && /tmp/pptx_env/bin/pip install python-pptx==1.0.2
    /tmp/pptx_env/bin/python submission/presentation_source/build_deck.py

Only real screenshots and diagram PNGs from submission/assets/ are used.
Evidence that does not exist yet (Orchestrate console, Bob history) is shown as a
clearly labelled placeholder box. Nothing here is a mock-up of an IBM product.
The slide text is mirrored in SLIDES.md.
"""
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "assets" / "screenshots"
DIAGS = ROOT / "assets" / "diagrams"
OUT = ROOT / "IBM_Bobathon_Presentation.pptx"

INK = RGBColor(0x16, 0x16, 0x16)
MUTED = RGBColor(0x52, 0x5B, 0x66)
BLUE = RGBColor(0x0F, 0x62, 0xFE)
SURFACE = RGBColor(0xF4, 0xF6, 0xF8)
BORDER = RGBColor(0xD0, 0xD5, 0xDB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xB2, 0x62, 0x00)
AMBER_BG = RGBColor(0xFF, 0xF4, 0xE0)
FONT = "Arial"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
TOTAL = 15


def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT):
    """paras: list of (text, size, bold, colour) or str."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, p in enumerate(paras):
        if isinstance(p, str):
            p = (p, 16, False, INK)
        t, size, bold, colour = p
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        para.space_after = Pt(6)
        run = para.add_run()
        run.text = t
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = colour
    return box


def rect(slide, x, y, w, h, fill=SURFACE, line=BORDER, shape=MSO_SHAPE.RECTANGLE, dash=False):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = line
    s.line.width = Pt(1)
    if dash:
        s.line.dash_style = 4  # dash
    s.shadow.inherit = False
    return s


def picture(slide, path, x, y, w, h):
    """Fit picture inside the box, preserving aspect ratio, centred."""
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    px, py = x + (w - pw) / 2, y + (h - ph) / 2
    slide.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))
    ring = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(px), Inches(py), Inches(pw), Inches(ph))
    ring.fill.background()
    ring.line.color.rgb = BORDER
    ring.line.width = Pt(0.75)
    ring.shadow.inherit = False


def placeholder(slide, x, y, w, h, ident, what):
    rect(slide, x, y, w, h, fill=AMBER_BG, line=AMBER, dash=True)
    text(
        slide, x + 0.1, y + 0.1, w - 0.2, h - 0.2,
        [
            ("PLACEHOLDER: " + ident, 13, True, AMBER),
            (what, 12, False, INK),
            ("Insert your real capture here. Not mocked.", 11, False, MUTED),
        ],
        anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER,
    )


def base(n, title, kicker=None, notes=None):
    n = len(prs.slides) + 1  # page number follows slide order
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.12))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE
    bar.line.fill.background()
    if kicker:
        text(s, 0.5, 0.25, 12.3, 0.35, [(kicker.upper(), 12, True, BLUE)])
    text(s, 0.5, 0.55, 12.3, 0.7, [(title, 30, True, INK)])
    text(s, 0.5, 7.08, 9, 0.3, [("MaleMitra  |  IBM Bobathon: Build for Bengaluru 2026", 10, False, MUTED)])
    text(s, 11.8, 7.08, 1.0, 0.3, [(f"{n} / {TOTAL}", 10, False, MUTED)], align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def card(slide, x, y, w, h, head, body, head_size=16, body_size=13):
    rect(slide, x, y, w, h)
    text(slide, x + 0.15, y + 0.12, w - 0.3, 0.5, [(head, head_size, True, INK)])
    text(slide, x + 0.15, y + 0.65, w - 0.3, h - 0.75, [(b, body_size, False, MUTED) for b in body])


# 1 Title -------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = INK
bg.line.fill.background()
text(s, 0.8, 1.7, 11.5, 1.2, [("MaleMitra  (ಮಳೆ ಮಿತ್ರ)", 54, True, WHITE)])
text(s, 0.8, 3.0, 11.5, 1.0, [("When the rain comes, the road you are sent down should already know it is flooded.", 22, False, RGBColor(0xC6, 0xD4, 0xFF))])
text(s, 0.8, 4.6, 11.5, 1.6, [
    ("Track: Smarter Streets, Better Living", 18, True, WHITE),
    ("IBM Bobathon: Build for Bengaluru 2026", 16, False, WHITE),
    ("Team: [TEAM INPUT REQUIRED: name, members, contact]", 16, False, RGBColor(0xFF, 0xC8, 0x7A)),
])
text(s, 0.8, 6.7, 11.5, 0.4, [("github.com/sakshit-allumolu/MaleMitra", 12, False, RGBColor(0x9A, 0xA5, 0xB1))])
s.notes_slide.notes_text_frame.text = (
    "Fill in team details (Q6, Q18). Track chosen: Smarter Streets, Better Living. "
    "Say the project name as 'Male' (rain) + 'Mitra' (friend)."
)

# 2 Problem (item 1 of 4: who experiences it, what needs to improve) --------
s = base(2, "The problem: who it hurts, what must improve", "1 of 4: The problem", notes=(
    "Required item 1: who experiences the problem and what needs to improve. No casualty, cost or response-time statistics on purpose: none were verified. "
    "The Bengaluru facts come from Wikipedia pages (URLs on the slide). Open the primary sources before quoting them from the stage."))
card(s, 0.5, 1.45, 4.0, 2.55, "Commuters and riders", [
    "See water but cannot report it to anyone who can act.",
    "Navigation does not know local hazards."], body_size=13)
card(s, 4.65, 1.45, 4.0, 2.55, "Control room", [
    "Scattered reports, no way to spot duplicates or judge credibility."], body_size=13)
card(s, 8.8, 1.45, 4.0, 2.55, "Field responders", [
    "Dispatched without a shared, current incident record."], body_size=13)
rect(s, 0.5, 4.15, 12.3, 0.95, fill=INK, line=INK)
text(s, 0.7, 4.2, 11.9, 0.85, [
    ("What must improve: one shared, verified picture that every route reacts to.", 18, True, WHITE)],
    anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.5, 5.3, 12.3, 1.7, [
    ("Why Bengaluru: monsoon runs June to September; 2022 had over 1,700 mm vs a mean of about 860 mm; built-up land rose from about 8 % (1973) to 87.6 % (2025); fewer than 200 of over 1,400 lakes and tanks survive.", 13, False, INK),
    ("Sources: en.wikipedia.org/wiki/Bengaluru | /Lakes_in_Bengaluru | /Infrastructure_in_Bengaluru. No casualty, cost or response-time claims.", 10, False, MUTED)])

# 3 Solution ------------------------------------------------------------------
s = base(3, "The prototype: one loop, report to reroute", "2 of 4: The prototype", notes=(
    "Required item 2: a working solution built using IBM Bob, with agentic AI where useful. "
    "Key design rule: an unverified report only adds a routing penalty scaled by reporter reputation and corroboration. "
    "Only an administrator can close a road, and only after field verification."))
card(s, 0.5, 1.6, 3.0, 3.4, "Citizen", [
    "Geotagged report with optional photo.",
    "Direct vs risk-aware vs alternative routes."], body_size=14)
card(s, 3.65, 1.6, 3.0, 3.4, "Control room", [
    "Triage, dispatch, and the only authority to close or reopen a road."], body_size=14)
card(s, 6.8, 1.6, 3.0, 3.4, "Responder", [
    "Verifies on site: water depth, impassable yes or no. Proposes clearance."], body_size=14)
card(s, 9.95, 1.6, 2.85, 3.4, "Ripple Engine", [
    "Shows where traffic goes after a closure."], body_size=14)
rect(s, 0.5, 5.3, 12.3, 1.2, fill=BLUE, line=BLUE)
text(s, 0.7, 5.4, 11.9, 1.0, [
    ("Built with IBM Bob. Plus an IBM watsonx Orchestrate agent that recommends the next step. A human approves every action.", 18, True, WHITE)],
    anchor=MSO_ANCHOR.MIDDLE)

# 4 Bob story, part 1 ----------------------------------------------------------
s = base(4, "The Bob story: how we built it", "3 of 4: The Bob story", notes=(
    "Required item 3: a short demo of how the team used Bob throughout development. This is the core participation requirement. "
    "Fill every [TEAM INPUT REQUIRED] with a REAL moment from your Bob history; do not invent any. "
    "Placeholders BOB-1, BOB-2 and BOB-3 are for your own captures. See docs/00_PARTICIPATION_REQUIREMENTS.md."))
beats = [
    ("1  Start", "First task given to Bob: [TEAM INPUT REQUIRED: real prompt and date]", "BOB-1", "First scaffolding prompt, with date"),
    ("2  Build and fix", "A real failure Bob helped fix: [TEAM INPUT REQUIRED: what broke, what diff Bob proposed]", "BOB-2 / BOB-3", "Failing test fixed, or a diff applied to a real file"),
    ("3  Review and trust", "Reviewed by [TEAM INPUT REQUIRED: who and how]. Checked by 242 passing tests.", "BOB-5", "Terminal: pytest backend/tests (242 passed) and git notes count"),
]
for i, (head, body, pid, pwhat) in enumerate(beats):
    x = 0.5 + i * 4.15
    rect(s, x, 1.45, 4.0, 1.95)
    text(s, x + 0.12, 1.5, 3.76, 0.45, [(head, 16, True, BLUE)])
    text(s, x + 0.12, 1.95, 3.76, 1.4, [(body, 12, False, INK)])
    placeholder(s, x, 3.55, 4.0, 2.2, pid, pwhat)
text(s, 0.5, 5.95, 12.3, 1.0, [
    ("Replace each amber box with your own capture. Show Bob at work for about 90 seconds in the video; script in docs/00 and docs/15.", 12, False, MUTED)])

# 5 Bob story, part 2 -----------------------------------------------------------
s = base(5, "Bob evidence in the repository", "3 of 4: The Bob story", notes=(
    "Verified: 7 local git notes recording 95 Bob edits (94 apply_diff, 1 insert_content) on 15 Nov 2026, 22:38 to 23:36 IST. "
    "Earlier-machine use and 'all commits on all branches were made with Bob' are team statements, not provable from the repo. "
    "The notes are local only; publish with: git push origin refs/notes/bob. Do not claim more than the evidence."))
text(s, 0.5, 1.5, 6.2, 5.3, [
    ("What the repository shows", 16, True, INK),
    ("95 recorded Bob edits across 7 commits, as small reviewable diffs.", 14, False, MUTED),
    ("Map component (32), routing module (27), responder workspace (22), demo guide (10), incident service (3), test (1).", 14, False, MUTED),
    ("How the output was checked", 16, True, INK),
    ("242 backend tests pass. Deterministic benchmark. Type-check and build in CI.", 14, False, MUTED),
    ("Team-stated, evidence pending", 16, True, AMBER),
    ("Earlier work on another machine; all commits on all branches. [TEAM INPUT REQUIRED: tasks, dates, reviewers]", 14, False, MUTED)])
placeholder(s, 7.0, 1.5, 5.8, 2.5, "BOB-4", "Bob task history from the earlier system, with dates")
placeholder(s, 7.0, 4.2, 5.8, 2.5, "BOB-5", "Terminal: git notes --ref=bob list | wc -l (7 in this clone)")

# 6 How it works -------------------------------------------------------------
s = base(5, "How it works", "2 of 4: The prototype", notes=(
    "State guards are enforced in incident_service.py. Reports within 10 m merge into one incident. "
    "Show SS11 to explain why the route differs."))
steps = ["Report", "Snap to road\nand merge", "Admin\ntriage", "Dispatch\nteam", "Field\nverify", "Admin\nauthorises\nclosure", "Routes\nre-plan", "Clearance,\nthen reopen"]
for i, label in enumerate(steps):
    x = 0.5 + i * 1.56
    shp = rect(s, x, 1.5, 1.42, 1.3, fill=BLUE if i == 5 else SURFACE, line=BLUE if i == 5 else BORDER)
    text(s, x, 1.5, 1.42, 1.3, [(label, 12, True, WHITE if i == 5 else INK)], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
picture(s, SHOTS / "SS11_citizen_route_compare.png", 0.5, 3.1, 7.4, 3.8)
text(s, 8.2, 3.2, 4.6, 3.6, [
    ("Every step is role-gated and written to an audit trail.", 15, True, INK),
    ("Closing a road increments the graph version, so every later route request sees it.", 14, False, MUTED),
    ("Screenshot: route comparison, shown offline with the label 'Graph fallback (OSRM unavailable)'.", 12, False, MUTED)])

# 6 Demo ---------------------------------------------------------------------
s = base(6, "The working product", "2 of 4: The prototype", notes=(
    "All six images are real captures from the running application on 15 Nov 2026. "
    "The responder capture is an empty state; retake with a populated queue if possible (EXT-5). "
    "Timeline rows visible in the audit are rule-based; LLM rows need ORCH-5."))
cells = [
    ("SS02_citizen_workspace.png", "Citizen: map, report, routes"),
    ("SS03_admin_control_room.png", "Control room: triage queue"),
    ("SS09_responder_field_tasks.png", "Responder: field tasks"),
    ("SS11_citizen_route_compare.png", "Route comparison"),
    ("SS07_ripple_engine.png", "Ripple Engine (synthetic trips)"),
    ("SS06_admin_audit_log.png", "System audit trail"),
]
for i, (f, cap) in enumerate(cells):
    col, row = i % 3, i // 3
    x, y = 0.5 + col * 4.15, 1.4 + row * 2.8
    picture(s, SHOTS / f, x, y, 4.0, 2.3)
    text(s, x, y + 2.3, 4.0, 0.3, [(cap, 11, False, MUTED)], align=PP_ALIGN.CENTER)

# 7 Architecture -------------------------------------------------------------
s = base(7, "Technical architecture", "2 of 4: The prototype", notes=(
    "Modular monolith: 11 routers, 13 service modules, 14 tables, 53 API operations. "
    "OSRM, TomTom and SMTP are optional and each has a fallback. Diagram is exported from docs/03."))
picture(s, DIAGS / "01_high_level_architecture.png", 0.5, 1.4, 12.3, 4.6)
text(s, 0.5, 6.15, 12.3, 0.8, [
    ("FastAPI + React/TypeScript, SQLite or PostgreSQL, Leaflet. Optional OSRM, TomTom and SMTP, each with a fallback. Agent reaches MaleMitra only through 8 API-key-protected tools.", 13, False, MUTED)])

# 8 Agentic AI ---------------------------------------------------------------
s = base(8, "Agentic AI: bounded autonomy", "2 of 4: Agentic AI where useful", notes=(
    "Be exact: only ONE agent is an LLM (watsonx Orchestrate). Incident Intelligence, Response Coordinator and Mobility are rule-based Python. "
    "No agent-to-agent coordination is implemented. Show ORCH-5 (LLM agent rows in the timeline) if available."))
picture(s, DIAGS / "04_agent_workflow.png", 0.5, 1.35, 12.3, 3.9)
card(s, 0.5, 5.3, 6.0, 1.65, "LLM agent (1)", [
    "watsonx Orchestrate: chooses tools, recommends one valid action."], head_size=14, body_size=12)
card(s, 6.8, 5.3, 6.0, 1.65, "Rule-based modules (3)", [
    "Incident Intelligence, Response Coordinator, Mobility. Python, not LLM."], head_size=14, body_size=12)

# 10 Orchestrate -------------------------------------------------------------
s = base(10, "IBM watsonx Orchestrate in the loop", "2 of 4: Agentic AI where useful", notes=(
    "Verified: agent YAML, 8-tool OpenAPI spec, 37 passing tests, guardrail smoke test, and on 15 Nov a live IAM token exchange and live chat call. "
    "The full tool-callback loop is team-stated and must be shown live (ORCH-3 to ORCH-6). "
    "The model name in the YAML is granite-3-8b-instruct; confirm it in the console (Q20). Crop the tunnel URL."))
picture(s, DIAGS / "06_orchestrate_integration.png", 0.5, 1.35, 7.6, 2.9)
text(s, 0.5, 4.4, 7.6, 2.6, [
    ("8 tools: map_to_edge, list_open_incidents, list_responder_availability, get_incident_context, compute_route, estimate_bpr_load, run_ripple_what_if, submit_recommendation.", 12, False, MUTED),
    ("Only submit_recommendation writes, and it stores a recommendation with requires_approval. It cannot change status.", 13, True, INK),
    ("Wrong-state action: rejected with 422, agent re-plans. Admin approve runs the normal gated workflow action.", 12, False, MUTED)])
placeholder(s, 8.4, 1.4, 4.4, 2.7, "ORCH-3 / ORCH-4", "MaleMitra panel showing Connected, then Ask agent and the recommendation card")
placeholder(s, 8.4, 4.25, 4.4, 2.7, "ORCH-1 / ORCH-2", "Orchestrate console: agent page and the 8 imported tools")

# 11 Innovation --------------------------------------------------------------
s = base(11, "What is different", "Innovation", notes=(
    "Be honest that the individual techniques (shortest path, BPR delay) are standard; the novelty is the governed closed loop. "
    "Agent quality has not been formally evaluated."))
card(s, 0.5, 1.6, 6.0, 2.4, "Closed loop, not just a map", [
    "Report, verification, closure and rerouting in one role-gated system."], body_size=14)
card(s, 6.8, 1.6, 6.0, 2.4, "Trust-weighted crowd data", [
    "Unverified reports add only a weighted penalty. Only an admin closes a road."], body_size=14)
card(s, 0.5, 4.2, 6.0, 2.4, "Ripple Engine", [
    "Shows second-order effects of a closure on 150 simulated trips."], body_size=14)
card(s, 6.8, 4.2, 6.0, 2.4, "Agentic but governed", [
    "The agent picks tools and reasons, but can only recommend. Every call is logged."], body_size=14)

# 12 Impact ------------------------------------------------------------------
s = base(12, "Impact: one measurable outcome", "4 of 4: The impact", notes=(
    "Use ONLY the command-line figures (python backend/eval_benchmark.py, seed 42, identical on three runs). "
    "The in-app benchmark page shows different time figures because it uses live graph state; the committed JSON shows +289.6 % and must not be quoted. "
    "No real-world baseline exists; K3 to K6 require measurement (docs/10)."))
rect(s, 0.5, 1.5, 3.1, 1.8, fill=INK, line=INK)
text(s, 0.5, 1.55, 3.1, 1.7, [("38  →  0", 34, True, WHITE), ("trips on the closed road (of 150)", 12, False, WHITE)], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
rect(s, 3.8, 1.5, 3.1, 1.8, fill=INK, line=INK)
text(s, 3.8, 1.55, 3.1, 1.7, [("+14.2 s", 34, True, WHITE), ("+3.9 % mean trip time", 12, False, WHITE)], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
text(s, 0.5, 3.5, 6.4, 3.4, [
    ("The one outcome: closed-road exposure fell from 25.3 % to 0 % of trips (simulation).", 14, True, INK),
    ("K2 detour cost: +14.2 s, 0 trips stranded.", 14, True, INK),
    ("K3 to K6 (report-to-closure time, duplicate ratio, agent acceptance, false closures): instrumented, baseline requires measurement.", 12, False, MUTED),
    ("20-node model, five neighbourhoods, 150 synthetic trips, seed 42. Not field data. Reproduce: python backend/eval_benchmark.py", 11, False, AMBER)])
picture(s, SHOTS / "SS07_ripple_engine.png", 7.2, 1.5, 5.6, 3.5)
text(s, 7.2, 5.1, 5.6, 0.6, [("Ripple view after a closure. Synthetic trips.", 11, False, MUTED)], align=PP_ALIGN.CENTER)

# 13 Feasibility -------------------------------------------------------------
s = base(13, "Feasible today, with a path to scale", "Feasibility and scalability", notes=(
    "Verified on 15 Nov 2026: pytest 242 passed; npm run build passes; backend started in a fresh Python 3.12 venv. "
    "Not run: PostgreSQL suite, Docker Compose, load test, accessibility audit. There are no frontend tests. "
    "CI lint currently has 1 known error (F821 'Set'); the fix awaits approval (Q17)."))
card(s, 0.5, 1.6, 6.0, 4.1, "Verified", [
    "242 backend tests passed.",
    "Frontend build passes.",
    "Backend starts from a fresh virtual environment, healthy with 20 nodes and 56 edges.",
    "53 API operations, 14 tables.",
    "Hosted instance health returned 200."], body_size=14)
card(s, 6.8, 1.6, 6.0, 4.1, "Scale path (designed, not load-tested)", [
    "PostgreSQL and multi-worker state sharing, tested with separate server processes.",
    "Self-hostable OSRM for city-wide routing.",
    "Docker, Render and a Code Engine deploy script.",
    "Next: rainfall data, larger network, Kannada UI, municipal integration."], body_size=14)
text(s, 0.5, 5.9, 12.3, 1.0, [
    ("Not yet done: PostgreSQL and Docker runs, load test, accessibility audit, frontend tests.", 13, True, AMBER)])

# 14 Responsible AI ----------------------------------------------------------
s = base(14, "Privacy and human review by design", "Safety: privacy and human review", notes=(
    "Known gap to mention if asked: the API exposes other citizens' names and ids inside evidence_list to signed-in citizens (docs/09 section 4.1). Unfixed. "
    "Prompt injection: citizen free text reaches the LLM; mitigated by recommend-only design, state gates and human approval, but not sanitised."))
card(s, 0.5, 1.6, 6.0, 4.4, "Implemented", [
    "Agent can only recommend. Approval is human.",
    "Recommendations must be valid for the incident's state; stale ones cannot be approved.",
    "Agent tools closed by default; API-key header, constant-time compare.",
    "Reporter name, email and phone are not returned to the agent.",
    "Every call logged and shown in the timeline and audit trail."], body_size=13)
card(s, 6.8, 1.6, 6.0, 4.4, "Recommended next", [
    "Sanitise and limit citizen text before it reaches the LLM.",
    "Mask other reporters in evidence_list (known gap).",
    "Evaluate agent quality on labelled incidents.",
    "Retention and deletion jobs; HttpOnly-cookie sessions.",
    "Dependency and penetration testing."], body_size=13)
text(s, 0.5, 6.2, 12.3, 0.7, [
    ("Demo accounts use a public password (demo123) and exist only when DEMO_MODE=true.", 12, False, MUTED)])

# 15 Closing -----------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = INK
bg.line.fill.background()
text(s, 0.8, 0.9, 11.5, 0.9, [("Why MaleMitra deserves recognition", 36, True, WHITE)])
text(s, 0.8, 2.1, 11.5, 3.2, [
    ("The problem: commuters, control room and responders on different channels.", 20, False, WHITE),
    ("The prototype: working and role-based, built with IBM Bob.", 20, False, WHITE),
    ("The Bob story: small reviewed diffs, checked by 242 passing tests.", 20, False, WHITE),
    ("The impact: 38 to 0 trips on a closed road in simulation. A human approves every agent action.", 20, False, WHITE)])
text(s, 0.8, 5.5, 11.5, 1.4, [
    ("Repository: github.com/sakshit-allumolu/MaleMitra (branch feature-demo)", 14, False, RGBColor(0xC6, 0xD4, 0xFF)),
    ("Hosted demo: [TEAM INPUT REQUIRED: final URL]", 14, False, RGBColor(0xFF, 0xC8, 0x7A)),
    ("Contact: [TEAM INPUT REQUIRED]", 14, False, RGBColor(0xFF, 0xC8, 0x7A))])
s.notes_slide.notes_text_frame.text = "Fill in URLs and contact before submitting (Q10, Q18)."

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
