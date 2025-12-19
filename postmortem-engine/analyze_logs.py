import os
import re
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
LOG_FILE = Path("logs_sample.csv")
ORDER_ID_REGEX = re.compile(r"(ORD-(?:PROC-)?\d+)")

# Load environment with Gemini key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not GEMINI_API_KEY:
    print("[WARN] GEMINI_API_KEY not set. LLM-based reports will be skipped.")
else:
    genai.configure(api_key=GEMINI_API_KEY)


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def extract_order_id(message: str):
    if not isinstance(message, str):
        return None
    m = ORDER_ID_REGEX.search(message)
    return m.group(1) if m else None


def load_logs() -> pd.DataFrame | None:
    if not LOG_FILE.exists():
        print(f"[ERROR] Log file not found: {LOG_FILE.resolve()}")
        return None

    df = pd.read_csv(LOG_FILE)

    if "timestamp [UTC]" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp [UTC]"])
    else:
        print("[WARN] 'timestamp [UTC]' column not found; using raw index")
        df["timestamp"] = pd.to_datetime(df.index)

    df["message"] = df["message"].astype(str)
    df["severityLevel"] = df["severityLevel"].fillna(0).astype(int)
    df["order_id"] = df["message"].apply(extract_order_id)

    df = df.sort_values("timestamp").reset_index(drop=True)

    print(f"Loaded {len(df)} rows from {LOG_FILE.name}")
    print("Columns:", list(df.columns))
    return df


def build_incidents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    df_orders = df[df["order_id"].notna()].copy()
    if df_orders.empty:
        print("No rows with order_id found in logs.")
        return []

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


def print_incidents(incidents: List[Dict[str, Any]]) -> None:
    if not incidents:
        print("No incidents detected.")
        return

    print(f"\nDetected {len(incidents)} order incidents.\n")

    for inc in incidents:
        print("=" * 80)
        print(f"Incident for order: {inc['order_id']}")
        print(f"  Status:    {inc['status']}")
        print(f"  Start:     {inc['start_time']}")
        print(f"  End:       {inc['end_time']}")
        print(f"  Duration:  {inc['duration_seconds']:.1f} seconds")
        print(f"  Log lines: {inc['event_count']}")
        if inc["failure_detail"]:
            print(f"  Failure reason: {inc['failure_detail']}")
        print("  Timeline:")
        for msg in inc["messages"]:
            print("   -", msg)
        print()

    print("=" * 80)
    print("End of incident summaries.")


def generate_postmortem_gemini(inc: Dict[str, Any]) -> str:
    """
    Use Google Gemini to generate a rich post-mortem.
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


def main():
    df = load_logs()
    if df is None:
        return

    incidents = build_incidents(df)
    print_incidents(incidents)

    failed = [inc for inc in incidents if inc["status"] == "FAILED"]
    if not failed:
        print("\nNo failed incidents found; no LLM post-mortems to generate.")
        return

    print("\n\n=== GEMINI-GENERATED POST-MORTEM REPORTS FOR FAILED INCIDENTS ===\n")

    for inc in failed[:3]:  # limit calls
        print(f"### Post-mortem for {inc['order_id']}\n")
        try:
            report = generate_postmortem_gemini(inc)
        except Exception as e:
            print(f"[ERROR] Gemini generation failed: {e}")
            break
        print(report)
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()