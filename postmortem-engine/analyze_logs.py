import pandas as pd
from pathlib import Path

# Just use the file in the same folder
LOG_FILE = Path("logs_sample.csv")

def load_logs():
    if not LOG_FILE.exists():
        print(f"Log file not found: {LOG_FILE}")
        return None

    df = pd.read_csv(LOG_FILE)
    print(f"Loaded {len(df)} rows from {LOG_FILE.name}")
    print("Columns:", list(df.columns))
    print()
    print("Sample rows:")
    print(df.head(10))
    return df

def main():
    df = load_logs()
    if df is None:
        return

    print("\n=== RAW LOGS LOADED. NEXT: we'll build incident summaries. ===")

if __name__ == "__main__":
    main()