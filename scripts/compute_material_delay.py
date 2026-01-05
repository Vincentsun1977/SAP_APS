import sys
from pathlib import Path
import pandas as pd


def compute(material: str, ref_date: str = "2026-01-16"):
    path = Path("data/raw/History.csv")
    if not path.exists():
        print("History.csv not found")
        return 2

    df = pd.read_csv(path, parse_dates=["Basic start date", "Basic finish date", "Actual finish date"], dayfirst=False)

    ref = pd.to_datetime(ref_date)
    start = ref - pd.Timedelta(days=90)

    df_mat = df[df["Material Number"] == material].copy()
    df_mat = df_mat[df_mat["Basic start date"].notna()]
    df_window = df_mat[(df_mat["Basic start date"] >= start) & (df_mat["Basic start date"] <= ref)]

    if df_window.empty:
        print(f"No history for {material} in window {start.date()} - {ref.date()}")
        return 0

    # compute delay days = (Actual finish date - Basic finish date). If Actual finish missing, treat as NaN
    df_window["basic_finish"] = pd.to_datetime(df_window["Basic finish date"], errors="coerce")
    df_window["actual_finish"] = pd.to_datetime(df_window["Actual finish date"], errors="coerce")
    df_window["delay_days"] = (df_window["actual_finish"] - df_window["basic_finish"]).dt.days

    # delayed if delay_days > 0
    df_window["is_delayed"] = df_window["delay_days"] > 0

    total = len(df_window)
    delayed = int(df_window["is_delayed"].sum())
    delay_rate = delayed / total if total > 0 else 0

    print(f"Material: {material}")
    print(f"Window: {start.date()} - {ref.date()} ({total} orders)")
    print(f"Delayed: {delayed} orders")
    print(f"Delay rate: {delay_rate:.4f} ({delay_rate*100:.1f}%)")
    print()
    # show details
    cols = ["Sales Order", "Sales Order Item", "Order", "Basic start date", "Basic finish date", "Actual finish date", "Order quantity (GMEIN)", "delay_days", "is_delayed"]
    print(df_window[cols].sort_values("Basic start date").to_string(index=False))

    return 0


if __name__ == '__main__':
    mat = sys.argv[1] if len(sys.argv) > 1 else 'CDX6091204R5002'
    ref = sys.argv[2] if len(sys.argv) > 2 else '2026-01-16'
    raise SystemExit(compute(mat, ref))
