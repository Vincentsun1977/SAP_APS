import sys
from pathlib import Path

import pandas as pd


def main(argv):
    in_path = Path(argv[0]) if argv else Path("data/raw/prediction_input.csv")
    if not in_path.exists():
        print(f"File not found: {in_path}")
        return 2

    df = pd.read_csv(in_path, dtype=str)

    # normalize Sales Order / Item to remove .0 floats
    for c in ["Sales Order", "Sales Order Item"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)

    before_missing = df['Order'].isna().sum() if 'Order' in df.columns else len(df)

    if 'Order' not in df.columns:
        df['Order'] = None

    # Fill Order where missing using Sales Order + Sales Order Item
    def make_order(row):
        if pd.notna(row['Order']) and str(row['Order']).strip() != 'nan' and str(row['Order']).strip() != '':
            return row['Order']
        so = str(row.get('Sales Order', '')).strip()
        item = str(row.get('Sales Order Item', '')).strip()
        if so and item:
            return f"{so}_{item}"
        if so:
            return so
        return None

    df['Order'] = df.apply(make_order, axis=1)

    after_missing = int(df['Order'].isna().sum())

    df.to_csv(in_path, index=False, encoding='utf-8')

    print(f"Backfill complete. Before missing: {before_missing}, After missing: {after_missing}")
    if after_missing > 0:
        miss_path = in_path.with_name(in_path.stem + "_order_missing_after_backfill.csv")
        df[df['Order'].isna()].to_csv(miss_path, index=False, encoding='utf-8')
        print("Remaining missing rows saved to:", miss_path)

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
