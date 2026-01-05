#!/usr/bin/env python3
"""Compute production_complexity distribution and locate target order"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer


def main(target_order: str = "504556134_2502"):
    print("=" * 70)
    print("PRODUCTION COMPLEXITY DISTRIBUTION ANALYSIS")
    print("=" * 70)
    
    # Load historical data
    print("\n1. Loading historical data...")
    loader = APSDataLoader("data/raw")
    df_history = loader.load_and_merge()
    
    # Load new orders
    print("2. Loading new orders...")
    input_path = Path("data/raw/prediction_input.csv")
    if not input_path.exists():
        print(f"   Warning: {input_path} not found. Using historical data only.")
        df_new = pd.DataFrame()
    else:
        df_new = pd.read_csv(input_path)
        
        # Standardize columns
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
        
        # Merge FG if needed
        try:
            if 'total_production_time' not in df_new.columns or 'constraint_factor' not in df_new.columns:
                fg_df = pd.read_csv('data/raw/FG.csv')
                df_new = df_new.merge(
                    fg_df[['Material', 'Total production Time', 'Constraint', 'earlist strart date', 'Production Line']],
                    left_on='material',
                    right_on='Material',
                    how='left'
                )
                if 'Constraint' in df_new.columns and 'constraint_factor' not in df_new.columns:
                    df_new = df_new.rename(columns={
                        'Constraint': 'constraint_factor',
                        'Total production Time': 'total_production_time',
                        'earlist strart date': 'earliest_start_days'
                    })
            
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
        except Exception as e:
            print(f"   Warning: Error merging FG/Capacity: {e}")
        
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
    
    # Combine and engineer features
    print("3. Engineering features...")
    if not df_new.empty:
        df_combined = pd.concat([df_history, df_new], ignore_index=True)
        df_combined = df_combined.sort_values('planned_start_date')
    else:
        df_combined = df_history
    
    engineer = APSFeatureEngineer(lookback_days=90)
    df_feat = engineer.transform(df_combined)
    
    # Separate historical and new
    if not df_new.empty:
        df_hist_feat = df_feat.iloc[:len(df_history)].copy()
        df_new_feat = df_feat.iloc[len(df_history):].copy()
        df_new_feat['production_number'] = df_new_feat['production_number'].astype(str)
    else:
        df_hist_feat = df_feat
        df_new_feat = pd.DataFrame()
    
    # Compute statistics
    print("\n" + "=" * 70)
    print("PRODUCTION COMPLEXITY STATISTICS")
    print("=" * 70)
    
    # Historical
    hist_complexity = df_hist_feat['production_complexity'].dropna()
    print(f"\nHistorical Orders (n={len(hist_complexity)}):")
    print(f"  Mean:   {hist_complexity.mean():.2f}")
    print(f"  Median: {hist_complexity.median():.2f}")
    print(f"  Std:    {hist_complexity.std():.2f}")
    print(f"  Min:    {hist_complexity.min():.2f}")
    print(f"  Max:    {hist_complexity.max():.2f}")
    
    print(f"\n  Percentiles:")
    for p in [10, 25, 50, 75, 90, 95, 99]:
        val = np.percentile(hist_complexity, p)
        print(f"    {p:2d}th: {val:6.2f}")
    
    # New orders
    if not df_new_feat.empty:
        new_complexity = df_new_feat['production_complexity'].dropna()
        print(f"\nNew Orders (n={len(new_complexity)}):")
        print(f"  Mean:   {new_complexity.mean():.2f}")
        print(f"  Median: {new_complexity.median():.2f}")
        print(f"  Std:    {new_complexity.std():.2f}")
        print(f"  Min:    {new_complexity.min():.2f}")
        print(f"  Max:    {new_complexity.max():.2f}")
        
        print(f"\n  Percentiles:")
        for p in [10, 25, 50, 75, 90, 95, 99]:
            val = np.percentile(new_complexity, p)
            print(f"    {p:2d}th: {val:6.2f}")
    
    # Locate target order
    print("\n" + "=" * 70)
    print(f"TARGET ORDER: {target_order}")
    print("=" * 70)
    
    if not df_new_feat.empty:
        target_row = df_new_feat[df_new_feat['production_number'] == target_order]
        
        if not target_row.empty:
            target_val = target_row['production_complexity'].iloc[0]
            
            if pd.notna(target_val):
                # Percentile in historical
                hist_percentile = (hist_complexity < target_val).sum() / len(hist_complexity) * 100
                
                # Percentile in new orders
                new_percentile = (new_complexity < target_val).sum() / len(new_complexity) * 100
                
                print(f"\nProduction Complexity: {target_val:.2f}")
                print(f"\nPosition in Historical Orders:")
                print(f"  Percentile: {hist_percentile:.1f}th")
                print(f"  Rank: {(hist_complexity < target_val).sum() + 1} / {len(hist_complexity)}")
                
                print(f"\nPosition in New Orders:")
                print(f"  Percentile: {new_percentile:.1f}th")
                print(f"  Rank: {(new_complexity < target_val).sum() + 1} / {len(new_complexity)}")
                
                # Interpretation
                print(f"\nInterpretation:")
                if hist_percentile >= 95:
                    print(f"  ⚠️  VERY HIGH - Top 5% of historical orders")
                elif hist_percentile >= 75:
                    print(f"  ⚠️  HIGH - Top 25% of historical orders")
                elif hist_percentile >= 50:
                    print(f"  ℹ️  ABOVE AVERAGE")
                else:
                    print(f"  ✓  BELOW AVERAGE")
                
                # Show similar orders
                print(f"\nSimilar Historical Orders (complexity ≈ {target_val:.0f} ± 5):")
                similar = df_hist_feat[
                    (df_hist_feat['production_complexity'] >= target_val - 5) &
                    (df_hist_feat['production_complexity'] <= target_val + 5)
                ]
                if not similar.empty:
                    delay_rate = similar['is_delayed'].mean() if 'is_delayed' in similar.columns else None
                    print(f"  Count: {len(similar)}")
                    if delay_rate is not None:
                        print(f"  Historical delay rate: {delay_rate:.1%}")
                else:
                    print(f"  No similar orders found")
            else:
                print(f"\n⚠️  production_complexity is NaN for this order")
                print(f"   Check constraint_factor and total_production_time values")
        else:
            print(f"\n⚠️  Order {target_order} not found in new orders")
            print(f"   Available orders: {df_new_feat['production_number'].head(10).tolist()}")
    else:
        print("\n⚠️  No new orders loaded")
    
    print("\n" + "=" * 70)
    
    return 0


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "504556134_2502"
    raise SystemExit(main(target))
