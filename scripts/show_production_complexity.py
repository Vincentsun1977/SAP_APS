#!/usr/bin/env python3
"""Show production_complexity components for a given production order (uses prediction pipeline flow)"""
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` imports work when running from scripts/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer


def main(prod_order_id: str):
    # Load new orders prepared for prediction
    input_path = Path("data/raw/prediction_input.csv")
    if not input_path.exists():
        print(f"Input file not found: {input_path}. Run cleaning/backfill steps first.")
        return

    df_new = pd.read_csv(input_path)

    # Load historical data
    df_history = APSDataLoader("data/raw").load_and_merge()

    # Standardize columns same as prediction pipeline
    column_mapping = {
        'Sales Order': 'sales_doc',
        'Sales Order Item': 'item',
        'Order': 'production_number',
        'Material Number': 'material',
        'Material description': 'material_description',
        'Order quantity (GMEIN)': 'order_quantity',
        'Basic start date': 'planned_start_date',
        'Basic finish date': 'planned_finish_date',
        'Prodn Supervisor': 'production_supervisor',
        'Production Line': 'production_line',
        'Total production Time': 'total_production_time',
        'Constraint': 'constraint_factor',
        'earlist strart date': 'earliest_start_days',
        'Capacity': 'line_capacity',
    }

    df_new = df_new.rename(columns=column_mapping)

    # Convert dates
    df_new['planned_start_date'] = pd.to_datetime(df_new.get('planned_start_date'), errors='coerce')
    df_new['planned_finish_date'] = pd.to_datetime(df_new.get('planned_finish_date'), errors='coerce')

    # Merge FG and Capacity if missing (predict script handles this)
    try:
        if 'total_production_time' not in df_new.columns:
            fg_df = pd.read_csv('data/raw/FG.csv')
            df_new = df_new.merge(
                fg_df[['Material', 'Total production Time', 'Constraint', 'earlist strart date', 'Production Line']],
                left_on='material',
                right_on='Material',
                how='left'
            )
            # normalize merged FG constraint column to `constraint_factor`
            if 'Constraint' in df_new.columns and 'constraint_factor' not in df_new.columns:
                df_new = df_new.rename(columns={'Constraint': 'constraint_factor', 'Total production Time': 'total_production_time', 'earlist strart date': 'earliest_start_days', 'Production Line': 'production_line'})

        if 'line_capacity' not in df_new.columns:
            capacity_df = pd.read_csv('data/raw/Capacity.csv')
            df_new = df_new.merge(
                capacity_df[['Production Line', 'Capacity']],
                left_on='production_line',
                right_on='Production Line',
                how='left',
                suffixes=('', '_cap')
            )
            df_new['line_capacity'] = df_new.get('Capacity')
    except Exception:
        pass

    # Basic features
    df_new['planned_duration_days'] = (
        df_new['planned_finish_date'] - df_new['planned_start_date']
    ).dt.days
    df_new['qty_capacity_ratio'] = df_new['order_quantity'] / df_new['line_capacity']
    df_new['expected_production_days'] = (
        df_new['order_quantity'] * df_new['total_production_time'] / df_new['line_capacity']
    )
    df_new['planned_start_month'] = df_new['planned_start_date'].dt.month
    df_new['planned_start_weekday'] = df_new['planned_start_date'].dt.weekday
    df_new['planned_start_quarter'] = df_new['planned_start_date'].dt.quarter
    df_new['planned_start_year'] = df_new['planned_start_date'].dt.year
    df_new['has_supervisor'] = df_new['production_supervisor'].notna().astype(int)

    # Combine with history and engineer features (same as pipeline)
    df_combined = pd.concat([df_history, df_new], ignore_index=True)
    df_combined = df_combined.sort_values('planned_start_date')

    engineer = APSFeatureEngineer(lookback_days=90)
    df_feat = engineer.transform(df_combined)

    # New orders are the last rows
    df_new_features = df_feat.tail(len(df_new)).copy()
    df_new_features['production_number'] = df_new_features['production_number'].astype(str)

    row = df_new_features[df_new_features['production_number'] == prod_order_id]

    if row.empty:
        print(f"No rows found for production order: {prod_order_id}")
        print("Available sample production_number values:")
        print(df_new_features['production_number'].head(20).tolist())
        sys.exit(1)

    cols = [
        'production_number', 'material', 'order_quantity', 'total_production_time',
        'constraint_factor', 'line_capacity', 'qty_capacity_ratio', 'expected_production_days',
        'production_complexity'
    ]

    available = [c for c in cols if c in df_new_features.columns]
    print(row[available].to_string(index=False))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/show_production_complexity.py <production_number>")
        sys.exit(1)

    prod_order = sys.argv[1]
    main(prod_order)
