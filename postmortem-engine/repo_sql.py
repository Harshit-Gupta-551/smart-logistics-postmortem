import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from models_sql import Incident, Postmortem

def upsert_incident(db: Session, inc: dict, source: str = "csv"):
    raw = json.dumps(inc.get("messages", []), ensure_ascii=False)

    existing = db.query(Incident).filter(Incident.order_id == inc["order_id"]).first()
    if existing:
        existing.status = inc["status"]
        existing.start_time = inc["start_time"]
        existing.end_time = inc["end_time"]
        existing.duration_seconds = float(inc["duration_seconds"])
        existing.failure_detail = inc.get("failure_detail")
        existing.event_count = int(inc["event_count"])
        existing.raw_messages = raw
        existing.source = source
    else:
        db.add(
            Incident(
                order_id=inc["order_id"],
                status=inc["status"],
                start_time=inc["start_time"],
                end_time=inc["end_time"],
                duration_seconds=float(inc["duration_seconds"]),
                failure_detail=inc.get("failure_detail"),
                event_count=int(inc["event_count"]),
                raw_messages=raw,
                source=source,
            )
        )

def list_incidents(db: Session, status: str | None = None, search: str | None = None):
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status)
    if search:
        q = q.filter(Incident.order_id.contains(search))
    return q.order_by(Incident.start_time.desc()).all()

def get_incident(db: Session, order_id: str):
    return db.query(Incident).filter(Incident.order_id == order_id).first()

def get_postmortem(db: Session, order_id: str, model_name: str):
    return db.query(Postmortem).filter(
        Postmortem.order_id == order_id,
        Postmortem.model_name == model_name
    ).first()

def upsert_postmortem(db: Session, order_id: str, model_name: str, text: str):
    pm = get_postmortem(db, order_id, model_name)
    if pm:
        pm.report_text = text
    else:
        db.add(Postmortem(order_id=order_id, model_name=model_name, report_text=text))

def kpis(db: Session):
    total = db.query(func.count(Incident.id)).scalar() or 0
    failed = db.query(func.count(Incident.id)).filter(Incident.status == "FAILED").scalar() or 0

    top_failure = (
        db.query(Incident.failure_detail, func.count(Incident.id).label("c"))
        .filter(Incident.failure_detail.isnot(None))
        .group_by(Incident.failure_detail)
        .order_by(func.count(Incident.id).desc())
        .first()
    )

    top_failure_detail = top_failure[0] if top_failure else None
    failure_rate = (failed / total) if total else 0.0

    return {
        "total_incidents": total,
        "failed_incidents": failed,
        "failure_rate": failure_rate,
        "top_failure_detail": top_failure_detail,
    }