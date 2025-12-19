import os
import re
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
# core logic (load logs, build incidents, call Gemini)
# ---------------- CONFIG ----------------
LOG_FILE = Path("logs_sample.csv")
ORDER_ID_REGEX = re.compile(r"(ORD-(?:PROC-)?\d+)")

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("[WARN] GEMINI_API_KEY not set. LLM-based reports will be disabled.")


# ------------- CORE FUNCTIONS ------------

def extract_order_id(message: str):
    """Extract order id like ORD-... or ORD-PROC-... from log message."""
    if not isinstance(message, str):
        return None
    m = ORDER_ID_REGEX.search(message)
    return m.group(1) if m else None


def load_logs() -> pd.DataFrame | None:
    """Load the exported logs CSV and prepare a DataFrame."""
    if not LOG_FILE.exists():
        print(f"[ERROR] Log file not found: {LOG_FILE.resolve()}")
        return None

    df = pd.read_csv(LOG_FILE)

    if "timestamp [UTC]" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp [UTC]"])
    else:
        df["timestamp"] = pd.to_datetime(df.index)

    df["message"] = df["message"].astype(str)
    df["severityLevel"] = df["severityLevel"].fillna(0).astype(int)
    df["order_id"] = df["message"].apply(extract_order_id)

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def build_incidents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Turn rows into incident objects grouped by order_id.
    """
    df_orders = df[df["order_id"].notna()].copy()
    incidents: List[Dict[str, Any]] = []

    for order_id, group in df_orders.groupby("order_id"):
        group = group.sort_values("timestamp")

        has_error = (group["severityLevel"] >= 3).any()
        status = "FAILED" if has_error else "SUCCESS"

        start_time = group["timestamp"].min()
        end_time = group["timestamp"].max()
        duration = (end_time - start_time).total_seconds()

        error_rows = group[group["severityLevel"] >= 3]
        failure_detail = None
        if not error_rows.empty:
            last_error_msg = error_rows.iloc[-1]["message"]
            m = re.search(r"detail=(.*)", last_error_msg)
            failure_detail = m.group(1).strip() if m else last_error_msg

        incidents.append(
            {
                "order_id": order_id,
                "status": status,
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration,
                "event_count": len(group),
                "failure_detail": failure_detail,
                "messages": list(group["message"]),
            }
        )

    return incidents


def get_incident_by_order_id(incidents: List[Dict[str, Any]], order_id: str) -> Dict[str, Any] | None:
    """Find a single incident by order_id."""
    for inc in incidents:
        if inc["order_id"] == order_id:
            return inc
    return None


def generate_postmortem_gemini(inc: Dict[str, Any]) -> str:
    """
    Use Gemini to generate a post-mortem report text for one incident.
    """
    if not GEMINI_API_KEY:
        return "[LLM DISABLED] GEMINI_API_KEY not configured."

    import json

    incident_json = json.dumps(
        {
            "order_id": inc["order_id"],
            "status": inc["status"],
            "start_time": str(inc["start_time"]),
            "end_time": str(inc["end_time"]),
            "duration_seconds": inc["duration_seconds"],
            "failure_detail": inc["failure_detail"],
            "timeline": inc["messages"],
        },
        indent=2,
    )

    prompt = f"""
You are a senior SRE/DevOps engineer helping write incident post-mortem reports
for a smart logistics platform running on Microsoft Azure.

Here is the structured incident data:

{incident_json}

Generate a detailed post-mortem with these sections:

1. Executive Summary (2–4 sentences, non-technical, for managers)
2. Impact
3. Technical Root Cause
4. Timeline of Events (bulleted, chronological)
5. Contributing Factors
6. Corrective and Preventive Actions (3–6 concrete items, each with priority P0/P1/P2)
7. Lessons Learned (3 key points)

Keep it focused on this single incident.
""".strip()

    model = genai.GenerativeModel(GEMINI_MODEL)
    resp = model.generate_content(prompt)
    return resp.text