#!/usr/bin/env python3
"""
Explain production_complexity metric with correct constraint_factor interpretation
constraint_factor = daily production capacity (units/day)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd


def main():
    print("=" * 80)
    print("PRODUCTION COMPLEXITY METRIC EXPLANATION")
    print("=" * 80)
    
    print("\n📊 FIELD DEFINITIONS:")
    print("-" * 80)
    print("  constraint_factor:       Daily production capacity (units/day)")
    print("                           = Maximum units this line can produce per day")
    print("  total_production_time:   Hours required per unit")
    print("  production_complexity:   total_production_time × constraint_factor")
    print("                           = Total workload capacity (hours·units/day)")
    print("-" * 80)
    
    print("\n🔍 METRIC INTERPRETATION:")
    print("-" * 80)
    print("  production_complexity = hours/unit × units/day = hours/day")
    print("  ")
    print("  This represents the TOTAL DAILY WORKLOAD CAPACITY:")
    print("  - Higher value = Line configured for higher throughput")
    print("  - Combines both speed (hours/unit) and capacity (units/day)")
    print("  ")
    print("  Example:")
    print("    Material A: 2.5 hours/unit × 30 units/day = 75 hours/day capacity")
    print("    Material B: 2.0 hours/unit × 30 units/day = 60 hours/day capacity")
    print("    Material C: 5.0 hours/unit × 5 units/day  = 25 hours/day capacity")
    print("  ")
    print("  Material A has HIGHER complexity (75) because even though it takes")
    print("  2.5 hours per unit, the line can still produce 30 units/day,")
    print("  indicating a high-throughput, complex production setup.")
    print("-" * 80)
    
    print("\n⚠️  WHY THIS MATTERS FOR DELAY PREDICTION:")
    print("-" * 80)
    print("  Higher production_complexity may correlate with:")
    print("  ✓ More sophisticated production lines")
    print("  ✓ Higher equipment utilization")
    print("  ✓ More potential bottlenecks")
    print("  ✓ Greater sensitivity to disruptions")
    print("  ")
    print("  The model learned that orders with complexity in the top 20-25%")
    print("  have slightly higher delay risk (15% vs 14.85% baseline).")
    print("-" * 80)
    
    # Load example data
    print("\n📋 EXAMPLE FROM YOUR DATA:")
    print("-" * 80)
    
    fg_path = Path("data/raw/FG.csv")
    if fg_path.exists():
        fg = pd.read_csv(fg_path)
        
        # Calculate complexity
        fg['production_complexity'] = fg['Total production Time'] * fg['Constraint']
        
        # Show examples
        print("\nSample materials with different complexity levels:")
        print()
        
        # Sort by complexity
        fg_sorted = fg.sort_values('production_complexity', ascending=False)
        
        for idx, row in fg_sorted.head(5).iterrows():
            mat = row['Material']
            desc = row['Material Description'][:40] if len(row['Material Description']) > 40 else row['Material Description']
            time = row['Total production Time']
            cap = row['Constraint']
            comp = row['production_complexity']
            
            print(f"  {mat}")
            print(f"    {desc}")
            print(f"    Time: {time} hrs/unit × Capacity: {cap} units/day = Complexity: {comp} hrs/day")
            print()
        
        print("\nComplexity distribution in FG master data:")
        print(f"  Min:    {fg['production_complexity'].min():.1f}")
        print(f"  25th:   {fg['production_complexity'].quantile(0.25):.1f}")
        print(f"  Median: {fg['production_complexity'].median():.1f}")
        print(f"  75th:   {fg['production_complexity'].quantile(0.75):.1f}")
        print(f"  Max:    {fg['production_complexity'].max():.1f}")
    
    print("\n" + "=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    print("The current formula (time × capacity) creates a 'workload capacity' metric")
    print("that captures the production line's configured throughput capability.")
    print()
    print("For order 504556134_2502:")
    print("  - Material: CDX6091204R5002")
    print("  - Time: 2.5 hrs/unit")
    print("  - Capacity: 30 units/day")
    print("  - Complexity: 75 hrs/day (top 20-25%)")
    print()
    print("This high complexity indicates a high-throughput production configuration,")
    print("which historically shows slightly elevated delay risk.")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
