from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from engine import (
    load_logs,
    build_incidents,
    get_incident_by_order_id,
    generate_postmortem_gemini,
)

app = FastAPI(
    title="Postmortem Engine API",
    description="AI-assisted incident and post-mortem service for Smart Logistics",
    version="1.0.0",
)


def _load_incident_data() -> List[Dict[str, Any]]:
    df = load_logs()
    if df is None:
        raise HTTPException(status_code=500, detail="Log file not found or unreadable")
    return build_incidents(df)


@app.get("/incidents")
def list_incidents():
    """
    Return a summary list of all incidents (per order_id).
    """
    incidents = _load_incident_data()
    # Only summary fields for the list
    summary = [
        {
            "order_id": inc["order_id"],
            "status": inc["status"],
            "start_time": str(inc["start_time"]),
            "end_time": str(inc["end_time"]),
            "duration_seconds": inc["duration_seconds"],
            "failure_detail": inc["failure_detail"],
            "event_count": inc["event_count"],
        }
        for inc in incidents
    ]
    return jsonable_encoder(summary)


@app.get("/incidents/{order_id}")
def get_incident(order_id: str):
    """
    Return full incident details for a specific order_id.
    """
    incidents = _load_incident_data()
    inc = get_incident_by_order_id(incidents, order_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return jsonable_encoder(inc)


@app.get("/incidents/{order_id}/postmortem")
def get_postmortem(order_id: str):
    """
    Generate a post-mortem report for a specific incident using Gemini.
    """
    incidents = _load_incident_data()
    inc = get_incident_by_order_id(incidents, order_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    report = generate_postmortem_gemini(inc)
    return {
        "order_id": order_id,
        "status": inc["status"],
        "failure_detail": inc["failure_detail"],
        "postmortem": report,
    }


# For running directly: python api.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=9000, reload=True)