import argparse
import sys
from pathlib import Path

import pandas as pd


def read_csv_fallback(path: Path):
    encodings = ["utf-8", "cp1252", "latin1"]
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise UnicodeDecodeError("Unable to read CSV with fallback encodings", path, 0, 1, "encoding")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = [c.strip() for c in df.columns]
    df.columns = cols

    # Split combined Production Line and Prodn Supervisor if present
    for col in list(df.columns):
        if col.lower().startswith("production line") and "prodn" in col.lower():
            # example: "Production Line(Prodn Supervisor)"
            parts = col.split("(")
            pl_col = parts[0].strip()
            sup = None
            if len(parts) > 1:
                sup = parts[1].replace(")", "").strip()
            df.rename(columns={col: pl_col}, inplace=True)
            if sup and sup not in df.columns:
                # try to extract supervisor values from column values if they include parentheses
                def extract_sup(v):
                    try:
                        s = str(v)
                        if "(" in s and ")" in s:
                            return s.split("(")[1].split(")")[0].strip()
                    except Exception:
                        pass
                    return None

                df[sup] = df[pl_col].apply(lambda v: extract_sup(v) if pd.notna(v) else None)

    # Common renames
    rename_map = {
        "Sales Doc.": "Sales Order",
        "Sales Doc": "Sales Order",
        "Item": "Sales Order Item",
        "Production Number": "Order",
        "Material": "Material Number",
        "Material Description": "Material description",
        "Basic start date(Production Start date)": "Basic start date",
        "Basic finish date(Delivery date)": "Basic finish date",
        "Basic start date": "Basic start date",
        "Basic finish date": "Basic finish date",
        "APS Qty": "Order quantity (GMEIN)",
        "TI Qty": "Order quantity (GMEIN)",
        "Serial Qty": "Order quantity (GMEIN)",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df.rename(columns={k: v}, inplace=True)

    # If there's a column named 'Production Line' and also 'Prodn Supervisor' inside values,
    # ensure separate columns exist
    if "Production Line" in df.columns and "Prodn Supervisor" not in df.columns:
        # sometimes values like 'VSC_20260105_01' exist in other cols; try no-op
        pass

    return df


def parse_dates(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            # replace '.' with '-' then parse
            df[c] = df[c].astype(str).str.replace(r"\.", "-", regex=True)
            df[c] = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/raw/new_orders.csv")
    p.add_argument("--fg", default="data/raw/FG.csv")
    p.add_argument("--capacity", default="data/raw/Capacity.csv")
    p.add_argument("--output", default="data/raw/new_orders_cleaned.csv")
    args = p.parse_args(argv)

    in_path = Path(args.input)
    fg_path = Path(args.fg)
    cap_path = Path(args.capacity)
    out_path = Path(args.output)

    if not in_path.exists():
        print(f"Input file not found: {in_path}")
        return 2

    df = read_csv_fallback(in_path)
    df = normalize_columns(df)

    # Prefer 'APS Qty' or 'TI Qty' for order quantity
    if "Order quantity (GMEIN)" not in df.columns:
        for cand in ["APS Qty", "TI Qty", "Serial Qty"]:
            if cand in df.columns:
                df.rename(columns={cand: "Order quantity (GMEIN)"}, inplace=True)
                break

    # Map Production Line and Prodn Supervisor from header or values
    # If 'Production Line' column contains values like 'VSC_20260105_01', try to isolate left token
    if "Production Line" in df.columns:
        df["Production Line"] = df["Production Line"].astype(str).str.split("_").str[0]

    # If a column named 'Prodn Supervisor' exists, keep it; else try to find from other columns
    if "Prodn Supervisor" not in df.columns:
        possible = [c for c in df.columns if 'supervisor' in c.lower() or 'fevor' in c.lower()]
        if possible:
            df.rename(columns={possible[0]: "Prodn Supervisor"}, inplace=True)

    # Standardize dates
    df = parse_dates(df, ["Basic start date", "Basic finish date"]) 

    # Merge FG
    if fg_path.exists():
        fg = pd.read_csv(fg_path)
        # FG uses 'Material' as column for material number
        if 'Material' in fg.columns:
            fg.rename(columns={'Material': 'Material Number'}, inplace=True)
        left_on = 'Material Number' if 'Material Number' in df.columns else None
        if left_on:
            df = df.merge(fg[['Material Number', 'Total production Time', 'Constraint', 'earlist strart date', 'Production Line']], on='Material Number', how='left', suffixes=(None, '_fg'))

    # Merge Capacity
    if cap_path.exists():
        cap = pd.read_csv(cap_path)
        if 'Production Line' in cap.columns and 'Capacity' in cap.columns:
            df = df.merge(cap, on='Production Line', how='left')

    # Prepare output columns
    out_cols = [
        'Sales Order', 'Sales Order Item', 'Order', 'Material Number', 'Material description',
        'Order quantity (GMEIN)', 'Basic start date', 'Basic finish date', 'Prodn Supervisor',
        'Production Line', 'Total production Time', 'Constraint', 'earlist strart date', 'Capacity'
    ]

    # Ensure all out_cols exist in dataframe
    for c in out_cols:
        if c not in df.columns:
            df[c] = None

    df[out_cols].to_csv(out_path, index=False, encoding='utf-8')

    # Report summary
    required = ['Material Number', 'Order', 'Order quantity (GMEIN)', 'Basic start date', 'Basic finish date', 'Production Line']
    missing = {c: int(df[c].isna().sum()) for c in required if c in df.columns}
    print("Cleaned file written:", out_path)
    print("Row count:", len(df))
    print("Missing counts for key fields:")
    for k, v in missing.items():
        print(f" - {k}: {v}")

    # Save a small missing report
    miss_rows = df[df[required].isna().any(axis=1)]
    if not miss_rows.empty:
        miss_path = out_path.with_name(out_path.stem + "_missing_rows.csv")
        miss_rows.to_csv(miss_path, index=False, encoding='utf-8')
        print("Missing rows saved to:", miss_path)

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
