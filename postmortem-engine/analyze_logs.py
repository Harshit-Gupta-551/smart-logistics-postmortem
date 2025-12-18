import pandas as pd
from pathlib import Path
import re

# CSV in this folder
LOG_FILE = Path("logs_sample.csv")

# Regex to extract order IDs like:
# - ORD-20251218150457
# - ORD-PROC-20251218150606
ORDER_ID_REGEX = re.compile(r"(ORD-(?:PROC-)?\d+)")


def extract_order_id(message: str) -> str | None:
    """Extract order id from log message, if present."""
    if not isinstance(message, str):
        return None
    match = ORDER_ID_REGEX.search(message)
    return match.group(1) if match else None


def load_logs() -> pd.DataFrame | None:
    """Load CSV exported from Application Insights."""
    if not LOG_FILE.exists():
        print(f"[ERROR] Log file not found: {LOG_FILE.resolve()}")
        return None

    df = pd.read_csv(LOG_FILE)

    # Normalize columns
    if "timestamp [UTC]" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp [UTC]"])
    else:
        print("[WARN] 'timestamp [UTC]' column not found; using raw index")
        df["timestamp"] = pd.to_datetime(df.index)

    df["message"] = df["message"].astype(str)
    df["severityLevel"] = df["severityLevel"].fillna(0).astype(int)

    # Extract order_id from message
    df["order_id"] = df["message"].apply(extract_order_id)

    # Sort by time
    df = df.sort_values("timestamp").reset_index(drop=True)

    print(f"Loaded {len(df)} rows from {LOG_FILE.name}")
    print("Columns:", list(df.columns))
    return df


def build_incidents(df: pd.DataFrame) -> list[dict]:
    """
    Group logs by order_id and build simple incident summaries.
    We treat any order_id that has an ERROR (severityLevel >= 3) as an incident.
    """
    df_orders = df[df["order_id"].notna()].copy()
    if df_orders.empty:
        print("No rows with order_id found in logs.")
        return []

    incidents: list[dict] = []

    for order_id, group in df_orders.groupby("order_id"):
        group = group.sort_values("timestamp")

        has_error = (group["severityLevel"] >= 3).any()
        status = "FAILED" if has_error else "SUCCESS"

        start_time = group["timestamp"].min()
        end_time = group["timestamp"].max()
        duration = (end_time - start_time).total_seconds()

        # Get last ERROR message as main failure reason (if any)
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


def print_incidents(incidents: list[dict]) -> None:
    """Pretty-print incident summaries to console."""
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


def classify_root_cause(failure_detail: str | None) -> str:
    """Very simple rule-based root cause classification."""
    if not failure_detail:
        return "Unknown cause"

    text = failure_detail.lower()
    if "inventory service unavailable" in text:
        return "Inventory service outage (dependency failure)"
    if "insufficient stock" in text:
        return "Inventory capacity / stock issue"
    if "courier service timeout" in text or "courier api timeout" in text:
        return "Courier API latency / timeout (third-party degradation)"
    return "Unknown / unclassified failure"


def generate_postmortem(inc: dict) -> str:
    """Generate a simple text post-mortem for one incident."""
    order_id = inc["order_id"]
    status = inc["status"]
    start = inc["start_time"]
    end = inc["end_time"]
    duration = inc["duration_seconds"]
    failure_detail = inc["failure_detail"]
    root_cause = classify_root_cause(failure_detail)

    # Build a simple narrative from the timeline
    timeline_lines = "\n".join(f"    - {m}" for m in inc["messages"])

    if status == "FAILED":
        outcome_text = f"The order *did not* complete successfully. Final status: {status}."
    else:
        outcome_text = f"The order completed successfully. Final status: {status}."

    summary = f"""
POST-MORTEM REPORT (Order: {order_id})

1. Summary
   - Impacted entity: Single order in demo environment
   - Time window: {start} → {end} (≈ {duration:.1f} seconds)
   - Outcome: {outcome_text}
   - Primary failure detail: {failure_detail or "N/A"}
   - Classified root cause: {root_cause}

2. Timeline of Events
{timeline_lines}

3. Technical Root Cause (Initial)
   - {root_cause}
   - Evidence:
     - {failure_detail or "No explicit error message in logs"}

4. Possible Preventive Actions (Suggestions)
   - For inventory-related failures:
     - Add monitoring on inventory service availability and stock thresholds.
     - Implement fallback logic (e.g., retry, alternate warehouse) before failing orders.
   - For courier/API timeouts:
     - Implement exponential backoff and retries for courier API calls.
     - Add timeout and circuit breaker patterns to avoid cascading failures.
   - General:
     - Include more structured context in logs (order value, region, user segment).
     - Add synthetic tests for critical flows (order → inventory → courier).

5. Notes
   - This report is auto-generated from Application Insights traces.
   - In a real system, multiple orders with similar patterns would be grouped into a higher-level incident.
""".strip()

    return summary


def main():
    df = load_logs()
    if df is None:
        return

    incidents = build_incidents(df)

    # 1) Print compact incident summaries (what you already saw)
    print_incidents(incidents)

    # 2) Generate post-mortem drafts for FAILED incidents
    failed = [inc for inc in incidents if inc["status"] == "FAILED"]

    if not failed:
        print("\nNo failed incidents found; no post-mortems to generate.")
        return

    print("\n\n=== AUTO-GENERATED POST-MORTEM DRAFTS FOR FAILED INCIDENTS ===\n")

    for inc in failed:
        report = generate_postmortem(inc)
        print(report)
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()