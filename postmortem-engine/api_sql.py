import json
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db_sql import SessionLocal
from repo_sql import upsert_incident, list_incidents, get_incident, upsert_postmortem, kpis, get_postmortem

# reuse your existing CSV+Gemini logic
from engine import load_logs, build_incidents, generate_postmortem_gemini, GEMINI_MODEL

app = FastAPI(
    title="Postmortem Engine API (Azure SQL)",
    description="Incidents + Postmortems stored in Azure SQL",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/refresh")
def refresh_from_csv():
    """
    Read logs_sample.csv -> build incidents -> upsert into Azure SQL.
    """
    df = load_logs()
    if df is None:
        raise HTTPException(status_code=500, detail="logs_sample.csv not found")

    incidents = build_incidents(df)

    db = SessionLocal()
    try:
        for inc in incidents:
            # Convert timestamps to Python datetime for SQL DateTime columns
            inc_for_db = dict(inc)
            inc_for_db["start_time"] = inc["start_time"].to_pydatetime() if hasattr(inc["start_time"], "to_pydatetime") else inc["start_time"]
            inc_for_db["end_time"] = inc["end_time"].to_pydatetime() if hasattr(inc["end_time"], "to_pydatetime") else inc["end_time"]

            upsert_incident(db, inc_for_db, source="csv")
        db.commit()
    finally:
        db.close()

    return {"refreshed": len(incidents)}

@app.get("/kpis")
def get_kpis():
    db = SessionLocal()
    try:
        return kpis(db)
    finally:
        db.close()

@app.get("/incidents")
def api_list_incidents(status: str | None = None, search: str | None = None):
    db = SessionLocal()
    try:
        rows = list_incidents(db, status=status, search=search)
        return [
            {
                "order_id": r.order_id,
                "status": r.status,
                "start_time": r.start_time.isoformat(sep=" "),
                "end_time": r.end_time.isoformat(sep=" "),
                "duration_seconds": r.duration_seconds,
                "failure_detail": r.failure_detail,
                "event_count": r.event_count,
                "source": r.source,
            }
            for r in rows
        ]
    finally:
        db.close()

@app.get("/incidents/{order_id}")
def api_get_incident(order_id: str):
    db = SessionLocal()
    try:
        r = get_incident(db, order_id)
        if not r:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {
            "order_id": r.order_id,
            "status": r.status,
            "start_time": r.start_time.isoformat(sep=" "),
            "end_time": r.end_time.isoformat(sep=" "),
            "duration_seconds": r.duration_seconds,
            "failure_detail": r.failure_detail,
            "event_count": r.event_count,
            "source": r.source,
            "messages": json.loads(r.raw_messages),
        }
    finally:
        db.close()

@app.get("/incidents/{order_id}/postmortem")
def api_get_postmortem(order_id: str, regenerate: bool = False):
    model_name = GEMINI_MODEL

    db = SessionLocal()
    try:
        inc = get_incident(db, order_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")

        if not regenerate:
            cached = get_postmortem(db, order_id, model_name)
            if cached:
                return {"order_id": order_id, "model": model_name, "cached": True, "postmortem": cached.report_text}

        # generate fresh
        inc_dict = {
            "order_id": inc.order_id,
            "status": inc.status,
            "start_time": inc.start_time.isoformat(),
            "end_time": inc.end_time.isoformat(),
            "duration_seconds": inc.duration_seconds,
            "failure_detail": inc.failure_detail,
            "event_count": inc.event_count,
            "messages": json.loads(inc.raw_messages),
        }
        report = generate_postmortem_gemini(inc_dict)
        upsert_postmortem(db, order_id, model_name, report)
        db.commit()

        return {"order_id": order_id, "model": model_name, "cached": False, "postmortem": report}
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_sql:app", host="0.0.0.0", port=9001, reload=True)