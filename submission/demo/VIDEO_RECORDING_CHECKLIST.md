# Video Recording Checklist

Script: [`docs/15_VIDEO_DEMO_SCRIPT.md`](../../docs/15_VIDEO_DEMO_SCRIPT.md). Portal limits for video length and size are not confirmed (Q16). Check them first.

## 1. Before recording

### Environment
- [ ] Start the backend and frontend as in [`06_SETUP_AND_INSTALLATION.md`](../../docs/06_SETUP_AND_INSTALLATION.md), with `DEMO_MODE=true` and a **clean database**.
- [ ] Open `/api/v1/health` and confirm `healthy`.
- [ ] Internet is on (map tiles come from OpenStreetMap).
- [ ] If you show the hosted app, open it first so it is awake: <https://malemitra.onrender.com>.

### The Bob story (core requirement, 1:15 in the script)
- [ ] BOB-1: your first Bob task, with its date, ready to show.
- [ ] BOB-2 and BOB-3: a real failure Bob helped fix, and a real diff Bob applied.
- [ ] BOB-4 (if you have it): Bob history from the earlier system, with dates.
- [ ] A 15-second screen recording of Bob making one small change (optional but strong).
- [ ] You can say who reviewed Bob's changes and how.
- [ ] You will not claim more than your evidence shows (the repo proves 95 edits on 15 Nov only).
- [ ] Nothing personal or confidential was sent to Bob, and none is visible on screen.

### Orchestrate (critical)
- [ ] Orchestrate agent `malemitra_incident_agent` exists and the 8 tools are imported.
- [ ] `PUBLIC_BASE_URL` points to a **reachable** URL. The tunnel was offline at audit time and changes on restart.
- [ ] Admin → *watsonx Orchestrate Agent* shows **Connected**.
- [ ] Do a full dry run: create a `reported` incident, click **Ask agent**, check that a recommendation card appears.
- [ ] Fallback prepared (see the backup plan in the script).

### Safety of the recording
- [ ] No API key, token or `.env` file visible. Close the editor tabs that show `.env`.
- [ ] The tunnel host is cropped, blurred or kept off screen.
- [ ] No personal email, only `*@malemitra.in` demo accounts.
- [ ] Notifications turned off (Do Not Disturb).
- [ ] Browser: 1280×720 or larger, zoom 100 %, bookmarks bar hidden.

### Content
- [ ] Bracketed `[TEAM INPUT REQUIRED]` parts of the script filled in (name, Bob story, URLs).
- [ ] You will say "simulation" when quoting 38 → 0.
- [ ] You will say the agent *recommends* and a human *approves*.
- [ ] Only CLI benchmark figures will be read aloud: 38 → 0, +14.2 s, +3.9 %.
- [ ] One timed rehearsal done.

## 2. Terminal commands to have ready

```bash
pytest backend/tests                       # ends with: 242 passed
python backend/eval_benchmark.py           # 38 -> 0 trips
git notes --ref=bob list | wc -l           # 7 in the audited clone
```

After running them, restore tracked files:

```bash
git checkout -- backend/app/data/benchmark_results.json backend/app/data/benchmark_results.csv
```

## 3. Screens in order

1. Title slide
2. Login (SS01)
3. Citizen: route compare (SS11), report a hazard
4. Admin: queue, review, assign (SS03)
5. Responder: claim, verify
6. Admin: authorise closure
7. Ripple view (SS07)
8. Terminal: benchmark
9. **Bob story:** BOB-1 (start) → BOB-2/BOB-3 (build and fix) → terminal `git notes`, `pytest`, BOB-4 (review and trust)
10. Orchestrate console (ORCH-1, ORCH-2) → panel (ORCH-3) → Ask agent (ORCH-4) → timeline (ORCH-5) → approve (ORCH-6)
11. KPI slide, limits slide
12. Closing slide with URLs

## 4. After recording

- [ ] Watch the full video once with sound.
- [ ] Check there are no secrets, tunnel hosts, personal emails or passwords on screen.
- [ ] Check that every number you said matches the documents.
- [ ] Check length and file size against the portal limits.
- [ ] Add captions if the portal allows them (accessibility).
- [ ] Save an original copy before uploading.
- [ ] Upload, then open the uploaded link in a private browser window.
- [ ] Tick the video items in [`14_FINAL_SUBMISSION_CHECKLIST.md`](../../docs/14_FINAL_SUBMISSION_CHECKLIST.md).
