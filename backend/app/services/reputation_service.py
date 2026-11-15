"""
Crowd-report credibility.

An unverified citizen report puts a *penalty* on a road in risk-aware routing (it never closes it; only an
admin can). That penalty used to be full strength whoever reported, so a single throw-away account could
steer everyone's routes. Now the penalty is scaled by how much we trust the report:

* reporter reputation - learned from history: incidents the reporter raised that a responder later
  confirmed count for them, ones the control room rejected count against them (withdrawn reports are
  neutral). Smoothed so a new account starts in the middle and a single event cannot swing it:
      rep = (confirmed + 1.5) / (confirmed + rejected + 3)
  Admins and responders are fully trusted.
* corroboration - independent reporters combine: weight = 1 - prod(1 - rep_i), but never above
  MAX_UNVERIFIED_WEIGHT, so a crowd of fresh accounts can't reach the strength of a verified hazard.
* a stored photo from that reporter raises their contribution by PHOTO_BONUS (capped at 1).
* human triage: once an admin has reviewed or dispatched the incident, it is at least TRIAGED_FLOOR.
* a responder's field verification (or any later state) is full strength, 1.0.

Limits (documented in the README): reputation is per account, so determined abuse with many aged
accounts is not prevented, and photos are not analysed - they only mean "someone attached a file".
"""
from typing import Dict, Iterable, Optional

from backend.app.models.database import get_db_connection
from backend.app.models.schemas import IncidentStatus, UserRole

PRIOR_CONFIRMED = 1.5
PRIOR_TOTAL = 3.0
PHOTO_BONUS = 0.2
MAX_UNVERIFIED_WEIGHT = 0.9
TRIAGED_FLOOR = 0.7

VERIFIED_STATES = (IncidentStatus.FIELD_VERIFIED, IncidentStatus.BLOCKED, IncidentStatus.CLEARANCE_PROPOSED)
TRIAGED_STATES = (IncidentStatus.UNDER_REVIEW, IncidentStatus.ASSIGNED)
UNVERIFIED_STATES = (IncidentStatus.REPORTED,) + TRIAGED_STATES
ACTIVE_STATES = UNVERIFIED_STATES + VERIFIED_STATES
CONFIRMED_STATES = VERIFIED_STATES + (IncidentStatus.CLEARED,)
WITHDRAWN_NOTE = "Withdrawn by reporter"


def _placeholders(items: Iterable) -> str:
    return ",".join("?" * len(list(items)))


def reputations(cursor, user_ids: Iterable[str]) -> Dict[str, float]:
    """Reputation in [0, 1] for each user id (staff = 1.0)."""
    ids = sorted({u for u in user_ids if u})
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    staff = {r["id"] for r in cursor.execute(
        f"SELECT id FROM users WHERE id IN ({ph}) AND role IN (?, ?)", (*ids, UserRole.ADMIN, UserRole.RESPONDER))}
    confirmed_ph = ",".join("?" * len(CONFIRMED_STATES))
    rows = cursor.execute(f"""
        SELECT r.reporter_id AS uid,
               COUNT(DISTINCT CASE WHEN i.status IN ({confirmed_ph}) THEN i.id END) AS confirmed,
               COUNT(DISTINCT CASE WHEN i.status = ? AND COALESCE(i.restriction_notes, '') != ? THEN i.id END) AS rejected
        FROM incident_reports r JOIN incidents i ON i.id = r.incident_id
        WHERE r.reporter_id IN ({ph})
        GROUP BY r.reporter_id
    """, (*CONFIRMED_STATES, IncidentStatus.REJECTED, WITHDRAWN_NOTE, *ids)).fetchall()
    stats = {r["uid"]: (r["confirmed"], r["rejected"]) for r in rows}
    out = {}
    for uid in ids:
        if uid in staff:
            out[uid] = 1.0
            continue
        c, rej = stats.get(uid, (0, 0))
        out[uid] = (c + PRIOR_CONFIRMED) / (c + rej + PRIOR_TOTAL)
    return out


def reputation(user_id: str) -> float:
    conn = get_db_connection()
    try:
        return reputations(conn.cursor(), [user_id]).get(user_id, PRIOR_CONFIRMED / PRIOR_TOTAL)
    finally:
        conn.close()


def incident_weights(cursor, only_edge: Optional[str] = None, only_incident: Optional[str] = None) -> Dict[str, dict]:
    """
    Credibility of every active incident: {incident_id: {"edge": edge_id, "weight": float, "basis": str}}.
    """
    q = (f"SELECT id, road_edge_id, status, reported_by_id FROM incidents "
         f"WHERE status IN ({_placeholders(ACTIVE_STATES)})")
    params = list(ACTIVE_STATES)
    if only_edge:
        q += " AND road_edge_id = ?"
        params.append(only_edge)
    if only_incident:
        q += " AND id = ?"
        params.append(only_incident)
    incs = cursor.execute(q, params).fetchall()
    if not incs:
        return {}

    ids = [i["id"] for i in incs]
    ph = ",".join("?" * len(ids))
    photo_by = {}   # (incident, reporter) -> has a stored photo
    for r in cursor.execute(
            f"SELECT incident_id, reporter_id, "
            f"MAX(CASE WHEN COALESCE(photo_url, '') LIKE '%/uploads/%' THEN 1 ELSE 0 END) AS photo "
            f"FROM incident_reports WHERE incident_id IN ({ph}) GROUP BY incident_id, reporter_id", ids):
        photo_by[(r["incident_id"], r["reporter_id"])] = bool(r["photo"])
    reporters: Dict[str, set] = {i["id"]: {i["reported_by_id"]} for i in incs}
    for (inc_id, uid) in photo_by:
        reporters[inc_id].add(uid)
    reps = reputations(cursor, {u for s in reporters.values() for u in s})

    out = {}
    for i in incs:
        if i["status"] in VERIFIED_STATES:
            out[i["id"]] = {"edge": i["road_edge_id"], "weight": 1.0, "basis": "verified by a responder"}
            continue
        miss = 1.0
        for uid in reporters[i["id"]]:
            r = reps.get(uid, PRIOR_CONFIRMED / PRIOR_TOTAL)
            if photo_by.get((i["id"], uid)):
                r = min(1.0, r + PHOTO_BONUS)
            miss *= (1.0 - r)
        weight = min(MAX_UNVERIFIED_WEIGHT, 1.0 - miss)
        basis = f"{len(reporters[i['id']])} reporter(s), reputation-weighted"
        if i["status"] in TRIAGED_STATES and weight < TRIAGED_FLOOR:
            weight, basis = TRIAGED_FLOOR, "triaged by the control room"
        out[i["id"]] = {"edge": i["road_edge_id"], "weight": round(weight, 3), "basis": basis}
    return out


def edge_weights(cursor, only_edge: Optional[str] = None) -> Dict[str, float]:
    """Hazard weight per road edge: the strongest active incident on it."""
    result: Dict[str, float] = {}
    for info in incident_weights(cursor, only_edge=only_edge).values():
        if info["edge"]:
            result[info["edge"]] = max(result.get(info["edge"], 0.0), info["weight"])
    return result


def edge_weight(edge_id: str) -> float:
    conn = get_db_connection()
    try:
        return edge_weights(conn.cursor(), only_edge=edge_id).get(edge_id, 1.0)
    finally:
        conn.close()
