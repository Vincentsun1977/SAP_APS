#!/usr/bin/env python3
"""Diagnose production_complexity formula by examining actual data relationships"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np


def main():
    print("=" * 80)
    print("PRODUCTION COMPLEXITY FORMULA DIAGNOSIS")
    print("=" * 80)
    
    # Load FG data
    fg_path = Path("data/raw/FG.csv")
    if not fg_path.exists():
        print("FG.csv not found")
        return 1
    
    fg = pd.read_csv(fg_path)
    
    print("\n📊 FG.csv FIELD STATISTICS:")
    print("-" * 80)
    print(f"\nTotal production Time (天/件):")
    print(f"  Min:    {fg['Total production Time'].min()}")
    print(f"  Max:    {fg['Total production Time'].max()}")
    print(f"  Mean:   {fg['Total production Time'].mean():.2f}")
    print(f"  Unique: {fg['Total production Time'].nunique()} values")
    print(f"  Values: {sorted(fg['Total production Time'].unique())}")
    
    print(f"\nConstraint (件/天):")
    print(f"  Min:    {fg['Constraint'].min()}")
    print(f"  Max:    {fg['Constraint'].max()}")
    print(f"  Mean:   {fg['Constraint'].mean():.2f}")
    print(f"  Unique: {fg['Constraint'].nunique()} values")
    print(f"  Values: {sorted(fg['Constraint'].unique())}")
    
    # Calculate implied daily capacity
    fg['implied_daily_capacity'] = 1 / fg['Total production Time']
    
    print(f"\nImplied Daily Capacity (1 / Total production Time):")
    print(f"  Min:    {fg['implied_daily_capacity'].min():.2f} 件/天")
    print(f"  Max:    {fg['implied_daily_capacity'].max():.2f} 件/天")
    print(f"  Mean:   {fg['implied_daily_capacity'].mean():.2f} 件/天")
    
    # Compare with Constraint
    print(f"\n🔍 RELATIONSHIP ANALYSIS:")
    print("-" * 80)
    print(f"\nConstraint vs Implied Capacity:")
    print(f"  Constraint is {fg['Constraint'].mean() / fg['implied_daily_capacity'].mean():.1f}x larger than implied capacity")
    print(f"  This suggests Constraint is NOT the actual daily capacity for this material")
    
    # Show examples
    print(f"\n📋 SAMPLE MATERIALS:")
    print("-" * 80)
    
    for idx, row in fg.head(10).iterrows():
        mat = row['Material']
        time = row['Total production Time']
        const = row['Constraint']
        impl_cap = 1 / time
        complexity = time * const
        
        print(f"\n{mat}:")
        print(f"  Total production Time: {time} 天/件")
        print(f"  Constraint:            {const} 件/天")
        print(f"  Implied capacity:      {impl_cap:.2f} 件/天 (= 1/{time})")
        print(f"  Current complexity:    {complexity} (= {time} × {const})")
        print(f"  ⚠️  Constraint is {const/impl_cap:.1f}x the implied capacity!")
    
    # Load historical data to check expected_production_days
    print(f"\n\n🔍 CHECKING expected_production_days CALCULATION:")
    print("-" * 80)
    
    from src.data_processing.aps_data_loader import APSDataLoader
    
    loader = APSDataLoader("data/raw")
    df = loader.load_and_merge()
    
    # Check a few samples
    sample = df[['material', 'order_quantity', 'total_production_time', 'constraint_factor', 
                 'line_capacity', 'expected_production_days']].head(10)
    
    print("\nSample historical orders:")
    for idx, row in sample.iterrows():
        qty = row['order_quantity']
        time = row['total_production_time']
        const = row['constraint_factor']
        line_cap = row['line_capacity']
        exp_days = row['expected_production_days']
        
        # Current formula: qty * time / line_capacity
        calc_days = qty * time / line_cap if line_cap > 0 else None
        
        print(f"\n  Order qty: {qty}, Time: {time} 天/件, Line cap: {line_cap}, Constraint: {const}")
        print(f"  Expected days (formula): {exp_days:.2f}")
        print(f"  Calculated (qty × time / line_cap): {calc_days:.2f}" if calc_days else "  N/A")
        print(f"  Simple (qty × time): {qty * time:.2f}")
        print(f"  Using constraint (qty / constraint): {qty / const:.2f}" if const > 0 else "  N/A")
    
    print("\n\n" + "=" * 80)
    print("DIAGNOSIS SUMMARY:")
    print("=" * 80)
    print("""
Based on the data analysis:

1. CONSTRAINT FIELD INTERPRETATION:
   - Constraint values (5, 30) are MUCH LARGER than implied capacity (1/time)
   - Constraint appears to be a CAPACITY BASELINE or COMPLEXITY FACTOR
   - NOT the actual daily capacity for producing this specific material

2. CURRENT FORMULA ISSUES:
   - production_complexity = time × constraint gives values like 60, 75, 90
   - This creates a "capacity-weighted time" metric
   - Higher values = materials that take longer AND have higher constraint factor

3. EXPECTED_PRODUCTION_DAYS:
   - Uses: qty × time / line_capacity
   - This seems more reasonable for actual scheduling

RECOMMENDATIONS:
A) Keep current formula if constraint is a "complexity/priority factor"
B) Change to: production_complexity = total_production_time / constraint_factor
   (relative complexity - how complex vs baseline capacity)
C) Change to: production_complexity = total_production_time × order_quantity
   (total workload for this order)
D) Use expected_production_days directly as complexity measure
""")
    
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
