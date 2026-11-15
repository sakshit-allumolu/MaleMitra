import logging
import json
import uuid
from typing import Dict, List, Optional, Any
from fastapi import HTTPException
from backend.app.timeutil import utcnow
from backend.app.config import settings
from backend.app.models.database import get_db_connection
from backend.app.models.schemas import IncidentStatus, UserRole
from backend.app.services.graph_service import road_graph, haversine_distance
from backend.app.services.ripple_service import ripple_engine
from backend.app.services import notification_service as notify
from backend.app.services import reputation_service as reputation

log = logging.getLogger("malemitra.incident")

class IncidentService:
    @staticmethod
    def get_all_incidents(role: str = "citizen", user_id: Optional[str] = None,
                          limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()

        # `id` breaks ties so LIMIT/OFFSET pages are stable (rows created in the same instant share created_at).
        sql, args = "SELECT * FROM incidents ORDER BY created_at DESC, id DESC", []
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            args = [limit, offset]
        cursor.execute(sql, args)
        rows = cursor.fetchall()

        # Batch the related lookups (one query each) instead of three per incident.
        ids = [r["id"] for r in rows]
        evidence_by_inc: Dict[str, list] = {}
        for i in range(0, len(ids), 500):  # stay under SQLite's bound-variable limit
            chunk = ids[i:i + 500]
            cursor.execute(
                f"SELECT * FROM incident_evidence WHERE incident_id IN ({','.join('?' * len(chunk))}) "
                "ORDER BY created_at ASC", chunk)
            for ev in cursor.fetchall():
                evidence_by_inc.setdefault(ev["incident_id"], []).append(dict(ev))
        cursor.execute("SELECT id, label FROM response_teams")
        team_labels = {t["id"]: t["label"] for t in cursor.fetchall()}
        resp_ids = list({r["assigned_responder_id"] for r in rows if r["assigned_responder_id"]})
        responder_names: Dict[str, str] = {}
        if resp_ids:
            cursor.execute(f"SELECT id, name FROM users WHERE id IN ({','.join('?' * len(resp_ids))})", resp_ids)
            responder_names = {u["id"]: u["name"] for u in cursor.fetchall()}

        incidents = []
        for r in rows:
            evidence_list = evidence_by_inc.get(r["id"], [])
            team_label = team_labels.get(r["assigned_team_id"]) if r["assigned_team_id"] else None
            responder_name = responder_names.get(r["assigned_responder_id"]) if r["assigned_responder_id"] else None

            summary_dict = None
            if r["agent_summary"]:
                try:
                    summary_dict = json.loads(r["agent_summary"])
                except Exception:
                    summary_dict = None
            
            # Sanitization for citizen privacy: hide reporter identity from OTHER citizens.
            # The original reporter always sees their own id and name.
            is_own = (r["reported_by_id"] == user_id)
            reporter_display = "Verified Citizen"
            if role in [UserRole.ADMIN, UserRole.RESPONDER] or is_own:
                reporter_display = r["reported_by_name"]
                
            inc_dict = {
                "id": r["id"],
                "road_edge_id": r["road_edge_id"],
                "road_name": r["road_name"],
                "lat": r["lat"],
                "lon": r["lon"],
                "type": r["type"],
                "severity": r["severity"],
                "status": r["status"],
                "confidence": r["confidence"],
                # Return real id only to admins/responders or the owner; others get "anonymous"
                "reported_by_id": r["reported_by_id"] if (role != UserRole.CITIZEN or is_own) else "anonymous",
                "reported_by_name": reporter_display,
                "is_mine": is_own,
                "reports_count": r["reports_count"],
                "assigned_team_id": r["assigned_team_id"],
                "assigned_team_label": team_label,
                "assigned_responder_id": r["assigned_responder_id"],
                "assigned_responder_name": responder_name,
                "verification_notes": r["verification_notes"],
                "water_depth_cm": r["water_depth_cm"],
                "restriction_notes": r["restriction_notes"],
                "is_blocked": bool(r["is_blocked"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "evidence_list": evidence_list,
                "agent_summary": summary_dict
            }
            incidents.append(inc_dict)
            
        conn.close()
        return incidents

    @staticmethod
    def count_incidents() -> int:
        conn = get_db_connection()
        try:
            return conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def get_incident_by_id(incident_id: str, role: str = "citizen") -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        r = cursor.fetchone()
        if not r:
            conn.close()
            return None
            
        cursor.execute("SELECT * FROM incident_evidence WHERE incident_id = ? ORDER BY created_at ASC", (incident_id,))
        evidence_rows = cursor.fetchall()
        evidence_list = [dict(ev) for ev in evidence_rows]
        
        team_label = None
        if r["assigned_team_id"]:
            cursor.execute("SELECT label FROM response_teams WHERE id = ?", (r["assigned_team_id"],))
            t_row = cursor.fetchone()
            if t_row:
                team_label = t_row["label"]
                
        responder_name = IncidentService._responder_name(cursor, r["assigned_responder_id"])

        summary_dict = None
        if r["agent_summary"]:
            try:
                summary_dict = json.loads(r["agent_summary"])
            except Exception:
                summary_dict = None
                
        inc_dict = {
            "id": r["id"],
            "road_edge_id": r["road_edge_id"],
            "road_name": r["road_name"],
            "lat": r["lat"],
            "lon": r["lon"],
            "type": r["type"],
            "severity": r["severity"],
            "status": r["status"],
            "confidence": r["confidence"],
            "reported_by_id": r["reported_by_id"] if role != UserRole.CITIZEN else "anonymous",
            "reported_by_name": r["reported_by_name"] if role != UserRole.CITIZEN else "Citizen Commuter",
            "reports_count": r["reports_count"],
            "assigned_team_id": r["assigned_team_id"],
            "assigned_team_label": team_label,
            "assigned_responder_id": r["assigned_responder_id"],
            "assigned_responder_name": responder_name,
            "verification_notes": r["verification_notes"],
            "water_depth_cm": r["water_depth_cm"],
            "restriction_notes": r["restriction_notes"],
            "is_blocked": bool(r["is_blocked"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "evidence_list": evidence_list,
            "agent_summary": summary_dict
        }
        conn.close()
        return inc_dict

    # Statuses in which an assigned incident keeps its responder / team occupied.
    FIELD_STATUSES = (
        IncidentStatus.ASSIGNED, IncidentStatus.FIELD_VERIFIED,
        IncidentStatus.BLOCKED, IncidentStatus.CLEARANCE_PROPOSED,
    )

    @staticmethod
    def _responder_name(cursor, responder_id: Optional[str]) -> Optional[str]:
        if not responder_id:
            return None
        cursor.execute("SELECT name FROM users WHERE id = ?", (responder_id,))
        row = cursor.fetchone()
        return row["name"] if row else None

    @staticmethod
    def _current_load(cursor, responder_id: str) -> List[str]:
        """Ids of field incidents the responder is currently working on."""
        placeholders = ",".join("?" * len(IncidentService.FIELD_STATUSES))
        cursor.execute(
            f"SELECT id FROM incidents WHERE assigned_responder_id = ? AND status IN ({placeholders}) ORDER BY created_at",
            (responder_id, *IncidentService.FIELD_STATUSES),
        )
        return [r["id"] for r in cursor.fetchall()]

    @staticmethod
    def _sync_team(cursor, team_id: Optional[str]) -> None:
        """A team is dispatched while it still has a field incident, otherwise available."""
        if not team_id:
            return
        placeholders = ",".join("?" * len(IncidentService.FIELD_STATUSES))
        cursor.execute(
            f"SELECT id FROM incidents WHERE assigned_team_id = ? AND status IN ({placeholders}) ORDER BY created_at LIMIT 1",
            (team_id, *IncidentService.FIELD_STATUSES),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE response_teams SET current_incident_id = ?, status = 'dispatched' WHERE id = ?", (row["id"], team_id))
        else:
            cursor.execute("UPDATE response_teams SET current_incident_id = NULL, status = 'available' WHERE id = ?", (team_id,))

    @staticmethod
    def get_responder_availability(team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every active responder with their team and whether they are free right now."""
        conn = get_db_connection()
        cursor = conn.cursor()
        query = ("SELECT u.id, u.name, u.team_id, t.label AS team_label FROM users u "
                 "LEFT JOIN response_teams t ON t.id = u.team_id "
                 "WHERE u.role = 'responder' AND u.active = 1")
        params: List[Any] = []
        if team_id:
            query += " AND u.team_id = ?"
            params.append(team_id)
        cursor.execute(query + " ORDER BY u.team_id, u.name", params)
        responders = []
        for u in cursor.fetchall():
            load = IncidentService._current_load(cursor, u["id"])
            responders.append({
                "id": u["id"], "name": u["name"], "team_id": u["team_id"], "team_label": u["team_label"],
                "is_free": not load, "active_incident_ids": load,
            })
        conn.close()
        return responders

    @staticmethod
    def _check_field_access(cursor, inc, user_id: str) -> None:
        """Responders may only act on their own incident, or on an unclaimed one in their team's queue."""
        cursor.execute("SELECT role, team_id FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        if not u or u["role"] != UserRole.RESPONDER:
            return  # admins (and unknown service callers) are not restricted
        if inc["assigned_responder_id"]:
            if inc["assigned_responder_id"] != user_id:
                raise HTTPException(status_code=403, detail="This incident is assigned to another responder.")
        elif inc["assigned_team_id"] and inc["assigned_team_id"] != u["team_id"]:
            raise HTTPException(status_code=403, detail="This incident belongs to another team.")

    ACTIVE_STATUSES = (
        IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW, IncidentStatus.ASSIGNED,
        IncidentStatus.FIELD_VERIFIED, IncidentStatus.BLOCKED, IncidentStatus.CLEARANCE_PROPOSED,
    )

    # Corroboration raises severity: this many independent reporters means at least this severity.
    # Only the count escalates it (a single reporter cannot talk a report up to critical).
    SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    ESCALATE_AT = ((5, "critical"), (3, "high"))

    @staticmethod
    def _escalated_severity(current: str, reports_count: int) -> str:
        target = current
        for threshold, severity in IncidentService.ESCALATE_AT:
            if reports_count >= threshold:
                target = severity
                break
        rank = IncidentService.SEVERITY_RANK
        return target if rank.get(target, 0) > rank.get(current, 0) else current

    @staticmethod
    def _nearby_open_incident(cursor, lat: float, lon: float):
        """Closest open incident within DUPLICATE_RADIUS_M of the point, as (distance_m, row), else None."""
        radius = settings.DUPLICATE_RADIUS_M
        if radius <= 0:
            return None
        placeholders = ",".join("?" * len(IncidentService.ACTIVE_STATUSES))
        cursor.execute(f"SELECT * FROM incidents WHERE status IN ({placeholders})", IncidentService.ACTIVE_STATUSES)
        best = None
        for row in cursor.fetchall():
            d = haversine_distance(lat, lon, row["lat"], row["lon"])
            if d <= radius and (best is None or d < best[0]):
                best = (d, row)
        return best

    @staticmethod
    def _merge_report(conn, cursor, inc, distance_m: float, user_id: str, user_name: str, lat: float, lon: float,
                      severity: str, description: str, evidence_note: Optional[str],
                      photo_url: Optional[str]) -> Dict[str, Any]:
        """Count a report on an existing open incident instead of creating a new one."""
        incident_id = inc["id"]
        cursor.execute("SELECT 1 FROM incident_reports WHERE incident_id = ? AND reporter_id = ?", (incident_id, user_id))
        if cursor.fetchone():
            # The same person reporting the same spot again adds no new information.
            conn.close()
            result = IncidentService.get_incident_by_id(incident_id, role="citizen")
            result.update({"merged": True, "already_reported": True})
            return result

        now = utcnow().isoformat()
        reports_count = inc["reports_count"] + 1
        new_severity = IncidentService._escalated_severity(inc["severity"], reports_count)

        cursor.execute("""
        INSERT INTO incident_reports (
            id, incident_id, reporter_id, reporter_name, lat, lon, description, evidence_note, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"rep-{uuid.uuid4().hex[:8]}", incident_id, user_id, user_name, lat, lon, description,
              evidence_note, photo_url, now))
        cursor.execute("""
        INSERT INTO incident_evidence (
            id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, user_id, user_name, "citizen_report",
              f"{description} (reported severity: {severity})", photo_url, now))
        cursor.execute("UPDATE incidents SET reports_count = ?, severity = ?, updated_at = ? WHERE id = ?",
                       (reports_count, new_severity, now, incident_id))

        detail = {"merged_into": incident_id, "distance_m": round(distance_m, 1), "reports_count": reports_count,
                  "severity": new_severity, "severity_escalated": new_severity != inc["severity"]}
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), incident_id, "incident_intelligence", "merge_report",
              json.dumps([f"coord:({lat},{lon})", f"reporter:{user_id}"]), json.dumps(detail), "simulated", 0, now))
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), user_id, user_name, "MERGE_REPORT", "incident", incident_id,
              json.dumps({"reports_count": inc["reports_count"], "severity": inc["severity"]}),
              json.dumps({"reports_count": reports_count, "severity": new_severity}), now))
        conn.commit()
        conn.close()

        if new_severity != inc["severity"] and inc["road_edge_id"]:
            road_graph.set_edge_hazard(inc["road_edge_id"], new_severity, water_depth_cm=20.0,
                                       weight=reputation.edge_weight(inc["road_edge_id"]))

        result = IncidentService.get_incident_by_id(incident_id, role="citizen")
        result["merged"] = True
        return result

    # ── notifications (queued inside the caller's transaction) ───────────────────
    @staticmethod
    def _notify_reporters(cursor, inc, kind: str, headline: str, detail: str, exclude_user_id: Optional[str] = None) -> None:
        """Tell every citizen who reported this incident (original + merged reports)."""
        cursor.execute("SELECT DISTINCT reporter_id FROM incident_reports WHERE incident_id = ?", (inc["id"],))
        ids = {r["reporter_id"] for r in cursor.fetchall()} | {inc["reported_by_id"]}
        road = inc["road_name"] or "the reported location"
        for uid in sorted(ids - {exclude_user_id}):
            notify.enqueue(cursor, uid, kind, f"MaleMitra: {headline}",
                           f"Your report about {road} (ref {inc['id']}): {detail}",
                           dedupe_key=f"{kind}:{inc['id']}:{uid}")

    @staticmethod
    def _notify_admins(cursor, inc, kind: str, headline: str, detail: str) -> None:
        cursor.execute("SELECT id FROM users WHERE role = 'admin' AND active = 1")
        road = inc["road_name"] or "unmapped road"
        for r in cursor.fetchall():
            notify.enqueue(cursor, r["id"], kind, f"MaleMitra control room: {headline}",
                           f"{road} (incident {inc['id']}): {detail}",
                           dedupe_key=f"{kind}:{inc['id']}:{r['id']}:{inc['updated_at']}")

    HAZARD_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

    @staticmethod
    def restore_graph_state() -> Dict[str, int]:
        """
        Rebuild the in-memory road graph (closures + reported hazards) from the database.

        The graph lives in process memory, so without this a restart/redeploy would silently
        reopen every road the control room had closed. Safe to call repeatedly: it resets the
        operational state first, then replays all active incidents.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(IncidentService.ACTIVE_STATUSES))
        cursor.execute(
            f"SELECT road_edge_id, severity, status, is_blocked, reports_count FROM incidents "
            f"WHERE road_edge_id IS NOT NULL AND status IN ({placeholders})",
            IncidentService.ACTIVE_STATUSES)
        rows = cursor.fetchall()
        weights = reputation.edge_weights(cursor)
        conn.close()

        blocked, hazards = set(), {}
        for r in rows:
            edge_id = r["road_edge_id"]
            if edge_id not in road_graph.edges:
                continue
            if r["status"] == IncidentStatus.BLOCKED and r["is_blocked"]:
                blocked.add(edge_id)
            cur = hazards.get(edge_id)
            if cur is None:
                hazards[edge_id] = [r["severity"], r["reports_count"] or 1]
            else:
                if IncidentService.HAZARD_RANK.get(r["severity"], 0) > IncidentService.HAZARD_RANK.get(cur[0], 0):
                    cur[0] = r["severity"]
                cur[1] += r["reports_count"] or 1

        with road_graph.lock:
            for edge in road_graph.edges.values():
                edge.is_blocked = False
                edge.hazard_severity = "none"
                edge.water_depth_cm = 0.0
                edge.reported_hazards_count = 0
                edge.hazard_weight = 1.0
            for edge_id in blocked:
                road_graph.edges[edge_id].is_blocked = True
            for edge_id, (severity, count) in hazards.items():
                edge = road_graph.edges[edge_id]
                edge.hazard_severity = severity
                edge.water_depth_cm = 20.0
                edge.reported_hazards_count = count
                edge.hazard_weight = weights.get(edge_id, 1.0)
            road_graph.graph_version += 1
        return {"blocked_edges": len(blocked), "hazard_edges": len(hazards)}

    @staticmethod
    def _active_incident_on_edge(cursor, edge_id: Optional[str], exclude_id: Optional[str] = None) -> Optional[str]:
        """Oldest still-open incident on the same road segment (None if there isn't one)."""
        if not edge_id:
            return None
        placeholders = ",".join("?" * len(IncidentService.ACTIVE_STATUSES))
        query = f"SELECT id FROM incidents WHERE road_edge_id = ? AND status IN ({placeholders})"
        params: List[Any] = [edge_id, *IncidentService.ACTIVE_STATUSES]
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)
        cursor.execute(query + " ORDER BY created_at ASC LIMIT 1", params)
        row = cursor.fetchone()
        return row["id"] if row else None

    @staticmethod
    def create_report(user_id: str, user_name: str, lat: float, lon: float,
                      inc_type: str, severity: str, description: str, 
                      evidence_note: Optional[str] = None, photo_url: Optional[str] = None) -> Dict[str, Any]:
        
        # Spatial edge mapping
        nearest_edge, dist_m, is_ambiguous = road_graph.find_nearest_edge(lat, lon)
        edge_id = nearest_edge.edge_id if nearest_edge else None
        road_name = nearest_edge.road_name if nearest_edge else f"Road near {lat:.4f}, {lon:.4f}"
        
        # Calculate initial confidence
        confidence = 0.85
        if not nearest_edge:
            confidence = 0.5  # outside the modelled streets: still logged for the control room, but not auto-priced
        elif is_ambiguous:
            confidence = 0.55
        elif dist_m > 300.0:
            confidence = 0.65
            
        now = utcnow().isoformat()
        incident_id = f"inc-{uuid.uuid4().hex[:8]}"
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Same spot as an open incident (within a few metres): count it there, don't open another
        nearby = IncidentService._nearby_open_incident(cursor, lat, lon)
        if nearby:
            return IncidentService._merge_report(
                conn, cursor, nearby[1], nearby[0], user_id, user_name, lat, lon,
                severity, description, evidence_note, photo_url)

        # Group with an incident that is already open on the same road segment
        duplicate_of = IncidentService._active_incident_on_edge(cursor, edge_id)

        if duplicate_of:
            recommendation = f"Possible duplicate of {duplicate_of} - corroborates it; review and reject or merge"
        elif not nearest_edge:
            recommendation = "Outside the modelled road network: confirm the location on site; no routing penalty applied"
        elif is_ambiguous:
            recommendation = "Triage review required before response assignment"
        else:
            recommendation = "Eligible for priority inspection"

        # Agent summary
        agent_summary = {
            "edge_mapped": edge_id,
            "distance_to_edge_m": round(dist_m, 1) if nearest_edge else None,
            "is_ambiguous": is_ambiguous,
            "confidence": confidence,
            "recommendation": recommendation,
            "duplicate_cluster": duplicate_of is not None,
            "duplicate_of": duplicate_of,
        }
        
        cursor.execute("""
        INSERT INTO incidents (
            id, road_edge_id, road_name, lat, lon, type, severity, status, 
            confidence, reported_by_id, reported_by_name, reports_count, 
            agent_summary, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            incident_id, edge_id, road_name, lat, lon, inc_type, severity, 
            IncidentStatus.REPORTED, confidence, user_id, user_name, 1, 
            json.dumps(agent_summary), now, now
        ))
        
        # Insert report entry
        report_id = f"rep-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
        INSERT INTO incident_reports (
            id, incident_id, reporter_id, reporter_name, lat, lon, description, evidence_note, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (report_id, incident_id, user_id, user_name, lat, lon, description, evidence_note, photo_url, now))
        
        # Insert evidence entry
        evidence_id = f"ev-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
        INSERT INTO incident_evidence (
            id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (evidence_id, incident_id, user_id, user_name, "citizen_report", description, photo_url, now))

        # Control room heads-up for serious new reports (queued in this transaction)
        if severity in ("high", "critical"):
            cursor.execute("SELECT id FROM users WHERE role = 'admin' AND active = 1")
            for adm in cursor.fetchall():
                notify.enqueue(cursor, adm["id"], "new_incident",
                               f"MaleMitra control room: new {severity} report",
                               f"{road_name} (incident {incident_id}): {description[:200]}",
                               dedupe_key=f"new_incident:{incident_id}:{adm['id']}")

        # Independent corroborating report: bump the original's report count
        if duplicate_of:
            cursor.execute("UPDATE incidents SET reports_count = reports_count + 1 WHERE id = ?", (duplicate_of,))
        
        # Log Agent Event
        event_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, incident_id, "incident_intelligence", "classify_and_map_edge",
            json.dumps([f"coord:({lat},{lon})", f"report:{report_id}"]),
            json.dumps(agent_summary), "simulated", 1, now
        ))
        
        # Log Audit Event
        audit_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id, user_id, user_name, "CREATE_REPORT", "incident", incident_id,
            None, json.dumps({"status": IncidentStatus.REPORTED, "edge_id": edge_id}), now
        ))
        
        conn.commit()
        conn.close()
        
        # Update unverified hazard score in graph (warning penalty, not closure)
        if edge_id:
            road_graph.set_edge_hazard(edge_id, severity, water_depth_cm=20.0,
                                       weight=reputation.edge_weight(edge_id))
            
        return IncidentService.get_incident_by_id(incident_id, role="citizen")

    @staticmethod
    def admin_review(incident_id: str, admin_id: str, admin_name: str, notes: str, severity: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot review incident in state '{inc['status']}'")
            
        now = utcnow().isoformat()
        new_severity = severity if severity else inc["severity"]
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, severity = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.UNDER_REVIEW, new_severity, now, incident_id))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), admin_id, admin_name, "ADMIN_REVIEW", "incident", incident_id,
            json.dumps({"status": inc["status"]}), json.dumps({"status": IncidentStatus.UNDER_REVIEW, "notes": notes}), now
        ))
        
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="admin")

    @staticmethod
    def admin_assign_team(incident_id: str, admin_id: str, admin_name: str, team_id: str, notes: str,
                          responder_id: Optional[str] = None) -> Dict[str, Any]:
        """Send an incident to a team's queue, or straight to one responder on that team."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.UNDER_REVIEW, IncidentStatus.ASSIGNED]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot assign team for incident in state '{inc['status']}'. Triage review must be confirmed first.")

        cursor.execute("SELECT 1 FROM response_teams WHERE id = ?", (team_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail=f"Unknown response team '{team_id}'")

        responder_name = None
        if responder_id:
            cursor.execute("SELECT name, team_id FROM users WHERE id = ? AND role = 'responder' AND active = 1", (responder_id,))
            resp = cursor.fetchone()
            if not resp or resp["team_id"] != team_id:
                conn.close()
                raise HTTPException(status_code=422, detail=f"'{responder_id}' is not an active responder on team '{team_id}'")
            responder_name = resp["name"]
            
        now = utcnow().isoformat()
        
        cursor.execute("""
        UPDATE incidents
        SET status = ?, assigned_team_id = ?, assigned_responder_id = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.ASSIGNED, team_id, responder_id, now, incident_id))

        IncidentService._sync_team(cursor, team_id)
        if inc["assigned_team_id"] != team_id:
            IncidentService._sync_team(cursor, inc["assigned_team_id"])  # reassigned: free the old team if idle
        
        target = f"Team {team_id}" + (f", responder {responder_name}" if responder_name else " (team queue)")
        # Evidence entry
        cursor.execute("""
        INSERT INTO incident_evidence (id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, admin_id, admin_name, "admin_assignment", f"Dispatched {target}: {notes}", now))
        
        # Agent Event
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), incident_id, "response_coordinator", "dispatch_responder",
            json.dumps([f"incident:{incident_id}", f"team:{team_id}"] + ([f"responder:{responder_id}"] if responder_id else [])),
            json.dumps({"assigned_team": team_id, "assigned_responder": responder_id, "status": "dispatched"}), "simulated", 0, now
        ))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), admin_id, admin_name, "ASSIGN_TEAM", "incident", incident_id,
            json.dumps({"status": inc["status"], "assigned_team_id": inc["assigned_team_id"],
                        "assigned_responder_id": inc["assigned_responder_id"]}),
            json.dumps({"status": IncidentStatus.ASSIGNED, "assigned_team_id": team_id,
                        "assigned_responder_id": responder_id}), now
        ))
        
        # Notifications: the dispatched responder (or the whole team queue) and the reporters
        task = f"{inc['road_name'] or 'a road'} - {inc['severity']} {inc['type'].replace('_', ' ')} (incident {incident_id}). {notes}"
        if responder_id:
            notify.enqueue(cursor, responder_id, "task_assigned", "MaleMitra: new task assigned to you", task,
                           dedupe_key=f"task_assigned:{incident_id}:{responder_id}:{now}")
        else:
            notify.enqueue_for_team(cursor, team_id, "task_queued", "MaleMitra: new incident in your team queue",
                                    task + " Claim it in the app if you are free.",
                                    dedupe_key=f"task_queued:{incident_id}:{now}")
        IncidentService._notify_reporters(
            cursor, inc, "report_assigned", "response team dispatched",
            "a field team has been dispatched to check it.")

        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="admin")

    @staticmethod
    def claim_incident(incident_id: str, responder_id: str, responder_name: str) -> Dict[str, Any]:
        """A free responder takes an unclaimed incident from their own team's queue."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")

        cursor.execute("SELECT team_id FROM users WHERE id = ?", (responder_id,))
        u = cursor.fetchone()
        team_id = u["team_id"] if u else None

        problem = None
        if inc["status"] != IncidentStatus.ASSIGNED or not inc["assigned_team_id"]:
            problem = f"Cannot claim an incident in state '{inc['status']}'."
        elif inc["assigned_team_id"] != team_id:
            problem = "This incident is in another team's queue."
        elif inc["assigned_responder_id"]:
            problem = "This incident is already assigned to a responder."
        elif IncidentService._current_load(cursor, responder_id):
            problem = "Finish your current task before taking a new one."
        if problem:
            conn.close()
            raise HTTPException(status_code=409 if "another" not in problem else 403, detail=problem)

        now = utcnow().isoformat()
        cursor.execute("UPDATE incidents SET assigned_responder_id = ?, updated_at = ? WHERE id = ?",
                       (responder_id, now, incident_id))
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), responder_id, responder_name, "CLAIM_INCIDENT", "incident", incident_id,
            json.dumps({"assigned_responder_id": None}), json.dumps({"assigned_responder_id": responder_id}), now
        ))
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="responder")

    @staticmethod
    def responder_verify(incident_id: str, responder_id: str, responder_name: str, 
                         findings: str, water_depth_cm: float, is_impassable: bool,
                         recommended_action: str, evidence_note: Optional[str] = None,
                         photo_url: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.ASSIGNED, IncidentStatus.FIELD_VERIFIED, IncidentStatus.BLOCKED]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot verify incident in state '{inc['status']}'. Must be assigned first.")
        try:
            IncidentService._check_field_access(cursor, inc, responder_id)
        except HTTPException:
            conn.close()
            raise
            
        now = utcnow().isoformat()
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, verification_notes = ?, water_depth_cm = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.FIELD_VERIFIED, findings, water_depth_cm, now, incident_id))
        
        # Insert evidence
        evidence_text = f"Field Inspection Findings: {findings}. Water Depth: {water_depth_cm}cm. Impassable: {is_impassable}. Recommendation: {recommended_action}."
        if evidence_note:
            evidence_text += f" Notes: {evidence_note}"
            
        cursor.execute("""
        INSERT INTO incident_evidence (
            id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, water_depth_cm, is_impassable, photo_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, responder_id, responder_name, "responder_inspection", evidence_text, water_depth_cm, 1 if is_impassable else 0, photo_url, now))
        
        # Agent Event
        cursor.execute("""
        INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), incident_id, "incident_intelligence", "field_evidence_verified",
            json.dumps([f"responder:{responder_id}", f"depth:{water_depth_cm}cm"]),
            json.dumps({"water_depth_cm": water_depth_cm, "is_impassable": is_impassable, "recommended_action": recommended_action}),
            "simulated", 1, now
        ))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), responder_id, responder_name, "RESPONDER_VERIFY", "incident", incident_id,
            json.dumps({"status": inc["status"]}), json.dumps({"status": IncidentStatus.FIELD_VERIFIED, "water_depth_cm": water_depth_cm}), now
        ))
        
        IncidentService._notify_admins(
            cursor, inc, "field_verified", "field inspection complete",
            f"{responder_name} found {water_depth_cm:g} cm of water ({'impassable' if is_impassable else 'passable'}); "
            f"recommends '{recommended_action}'. Review and authorize or monitor.")
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="responder")

    @staticmethod
    def responder_propose_clearance(incident_id: str, responder_id: str, responder_name: str, findings: str, evidence_note: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        if inc["status"] not in [IncidentStatus.BLOCKED, IncidentStatus.FIELD_VERIFIED, IncidentStatus.ASSIGNED]:
            conn.close()
            raise HTTPException(status_code=409, detail=f"Cannot propose clearance for incident in state '{inc['status']}'")
        try:
            IncidentService._check_field_access(cursor, inc, responder_id)
        except HTTPException:
            conn.close()
            raise
            
        now = utcnow().isoformat()
        
        cursor.execute("""
        UPDATE incidents 
        SET status = ?, verification_notes = ?, updated_at = ?
        WHERE id = ?
        """, (IncidentStatus.CLEARANCE_PROPOSED, findings, now, incident_id))
        
        # Add evidence
        cursor.execute("""
        INSERT INTO incident_evidence (id, incident_id, submitted_by, submitter_name, evidence_type, text_notes, water_depth_cm, is_impassable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"ev-{uuid.uuid4().hex[:8]}", incident_id, responder_id, responder_name, "clearance_evidence", f"Clearance proposal: {findings}", 5.0, 0, now))
        
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), responder_id, responder_name, "PROPOSE_CLEARANCE", "incident", incident_id,
            json.dumps({"status": inc["status"]}), json.dumps({"status": IncidentStatus.CLEARANCE_PROPOSED}), now
        ))
        
        IncidentService._notify_admins(
            cursor, inc, "clearance_proposed", "clearance proposed",
            f"{responder_name} reports the road is clear: {findings[:200]}. Authorize reopening if satisfied.")
        conn.commit()
        conn.close()
        return IncidentService.get_incident_by_id(incident_id, role="responder")

    @staticmethod
    def admin_authorize_restriction(incident_id: str, admin_id: str, admin_name: str, 
                                     action: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Admin Authorization:
        - action == 'authorize_block': Sets incident to BLOCKED, sets edge.is_blocked = True, increments graph_version
        - action == 'authorize_reopen': Sets incident to CLEARED, sets edge.is_blocked = False, increments graph_version
        - action == 'reject': Sets incident to REJECTED, clears edge hazard
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")
            
        edge_id = inc["road_edge_id"]
        now = utcnow().isoformat()
        
        if action == "authorize_block":
            if inc["status"] != IncidentStatus.FIELD_VERIFIED:
                conn.close()
                raise HTTPException(status_code=409, detail=f"Cannot authorize blockage on incident in status '{inc['status']}'. A responder must field-verify it first.")
                
            cursor.execute("""
            UPDATE incidents 
            SET status = ?, is_blocked = 1, restriction_notes = ?, updated_at = ?
            WHERE id = ?
            """, (IncidentStatus.BLOCKED, notes or "Authorized road closure by Monsoon Control Room.", now, incident_id))
            
            # Apply hard exclusion to RoadGraph
            if edge_id:
                road_graph.set_edge_restriction(edge_id, is_blocked=True, notes=notes)

            # ── Auto-trigger ripple simulation ────────────────────────────
            # Run immediately so all clients see updated congestion on next poll.
            # Runs in-process (synchronous) — takes ~8ms on the 20-node graph.
            try:
                ripple_engine.run_for_current_state(persist=False)  # shared after commit (we hold the write lock)
            except Exception as re:
                log.warning(f"[Ripple] Auto-run after blockage failed: {re}")

            # Log Agent Event
            cursor.execute("""
            INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), incident_id, "mobility", "invalidate_route_cache_and_block_edge",
                json.dumps([f"incident:{incident_id}", f"edge:{edge_id}"]),
                json.dumps({"blocked_edge_id": edge_id, "graph_version": road_graph.graph_version}),
                "simulated", 0, now
            ))
            
        elif action == "authorize_reopen":
            if inc["status"] != IncidentStatus.CLEARANCE_PROPOSED:
                conn.close()
                raise HTTPException(status_code=409, detail=f"Cannot authorize reopening of incident in status '{inc['status']}'. A responder must propose clearance first.")

            cursor.execute("""
            UPDATE incidents 
            SET status = ?, is_blocked = 0, restriction_notes = ?, updated_at = ?
            WHERE id = ?
            """, (IncidentStatus.CLEARED, notes or "Authorized road reopening after verification.", now, incident_id))
            
            # Release the team only if it has no other field incident left
            IncidentService._sync_team(cursor, inc["assigned_team_id"])
                
            # Reopen edge on RoadGraph
            if edge_id:
                road_graph.set_edge_restriction(edge_id, is_blocked=False, notes=notes)
                road_graph.clear_edge_hazard(edge_id)

            # ── Auto-trigger ripple simulation after reopening ────────────
            try:
                ripple_engine.run_for_current_state(persist=False)  # shared after commit (we hold the write lock)
            except Exception as re:
                log.warning(f"[Ripple] Auto-run after reopen failed: {re}")

            cursor.execute("""
            INSERT INTO agent_events (id, incident_id, agent, action, input_refs, result, data_mode, requires_approval, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), incident_id, "mobility", "reopen_road_and_restore_capacity",
                json.dumps([f"incident:{incident_id}", f"edge:{edge_id}"]),
                json.dumps({"reopened_edge_id": edge_id, "graph_version": road_graph.graph_version}),
                "simulated", 0, now
            ))
            
        elif action == "reject":
            if inc["status"] not in [IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW]:
                conn.close()
                raise HTTPException(status_code=409, detail=f"Cannot reject incident in status '{inc['status']}'. Only reported / under-review incidents can be rejected.")
            cursor.execute(
                "UPDATE incidents SET status = ?, is_blocked = 0, restriction_notes = ?, updated_at = ? WHERE id = ?",
                (IncidentStatus.REJECTED, notes or "Rejected by control room (duplicate or invalid report).", now, incident_id)
            )
            # Keep the hazard/closure on the road if another open incident still covers it
            if edge_id and not IncidentService._active_incident_on_edge(cursor, edge_id, exclude_id=incident_id):
                road_graph.clear_edge_hazard(edge_id)
        else:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Unknown restriction action '{action}'")
            
        # Audit
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), admin_id, admin_name, f"AUTHORIZE_{action.upper()}", "incident", incident_id,
            json.dumps({"status": inc["status"], "is_blocked": inc["is_blocked"]}),
            json.dumps({"action": action, "graph_version": road_graph.graph_version}), now
        ))
        
        if action == "authorize_block":
            IncidentService._notify_reporters(
                cursor, inc, "road_closed", "road closed",
                "the control room has closed this road. Routes in MaleMitra now avoid it.")
            if inc["assigned_responder_id"]:
                notify.enqueue(cursor, inc["assigned_responder_id"], "closure_authorized",
                               "MaleMitra: closure authorized",
                               f"The control room authorized closing {inc['road_name'] or 'the road'} (incident {incident_id}).",
                               dedupe_key=f"closure_authorized:{incident_id}:{now}")
        elif action == "authorize_reopen":
            IncidentService._notify_reporters(
                cursor, inc, "road_reopened", "road reopened",
                "the road has been cleared and reopened. Thank you for reporting.")
            if inc["assigned_responder_id"]:
                notify.enqueue(cursor, inc["assigned_responder_id"], "reopen_authorized",
                               "MaleMitra: reopening authorized",
                               f"Reopening of {inc['road_name'] or 'the road'} (incident {incident_id}) was authorized. Task closed.",
                               dedupe_key=f"reopen_authorized:{incident_id}:{now}")
        elif action == "reject":
            IncidentService._notify_reporters(
                cursor, inc, "report_rejected", "report closed",
                "the control room reviewed this report and closed it (duplicate or not confirmed). "
                "If you think this is wrong, please report again with more detail.")
        conn.commit()
        conn.close()
        if action in ("authorize_block", "authorize_reopen"):
            ripple_engine.publish_last()
        return IncidentService.get_incident_by_id(incident_id, role="admin")

    @staticmethod
    def withdraw_report(incident_id: str, user_id: str) -> Dict[str, Any]:
        """
        Citizen withdraws their own report.
        Rules:
          - Only the original reporter can withdraw.
          - Only allowed when status is 'reported' or 'under_review'
            (once field-verified or blocked, control room must handle it).
          - Clears the edge hazard from the graph so routing is not affected.
          - Sets status to 'rejected' (re-uses existing terminal status)
            with a restriction_notes label of 'Withdrawn by reporter'.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc:
            conn.close()
            raise HTTPException(status_code=404, detail="Incident not found")

        if inc["reported_by_id"] != user_id:
            conn.close()
            raise HTTPException(status_code=403, detail="You can only withdraw your own reports")

        if inc["reports_count"] > 1:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail="Other citizens have also reported this hazard, so it can't be withdrawn. "
                       "Contact the control room if it is wrong.")

        withdrawable = {IncidentStatus.REPORTED, IncidentStatus.UNDER_REVIEW}
        if inc["status"] not in withdrawable:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail=f"Cannot withdraw a report with status '{inc['status']}'. "
                       f"Only reports that are 'reported' or 'under_review' can be withdrawn."
            )

        now = utcnow().isoformat()
        cursor.execute(
            "UPDATE incidents SET status = ?, restriction_notes = ?, updated_at = ? WHERE id = ?",
            (IncidentStatus.REJECTED, "Withdrawn by reporter", now, incident_id)
        )

        # Clear edge hazard so routing is unaffected (unless another open incident still covers the road)
        edge_id = inc["road_edge_id"]
        if edge_id and not IncidentService._active_incident_on_edge(cursor, edge_id, exclude_id=incident_id):
            road_graph.clear_edge_hazard(edge_id)

        # Audit trail
        cursor.execute("""
        INSERT INTO audit_events (id, actor_id, actor_name, action, entity_type, entity_id, before_state, after_state, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), user_id, inc["reported_by_name"], "WITHDRAW_REPORT",
            "incident", incident_id,
            json.dumps({"status": inc["status"]}),
            json.dumps({"status": IncidentStatus.REJECTED, "note": "Withdrawn by reporter"}),
            now
        ))

        conn.commit()
        conn.close()
        return {"message": "Report withdrawn successfully", "incident_id": incident_id}

incident_service = IncidentService()
