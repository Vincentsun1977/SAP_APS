#!/usr/bin/env python3
"""Compare predictions between old and new models"""
import pandas as pd
from pathlib import Path


def main():
    old_path = Path("predictions/results.csv")
    new_path = Path("predictions/results_new_model.csv")
    
    if not old_path.exists() or not new_path.exists():
        print("Missing prediction files")
        return 1
    
    df_old = pd.read_csv(old_path)
    df_new = pd.read_csv(new_path)
    
    print("=" * 80)
    print("MODEL PREDICTION COMPARISON")
    print("=" * 80)
    
    print("\n📊 OVERALL STATISTICS:")
    print("-" * 80)
    print(f"{'Metric':<30} {'Old Model':<20} {'New Model':<20} {'Change'}")
    print("-" * 80)
    
    # Risk distribution
    for risk in ['高风险', '中风险', '低风险']:
        old_count = (df_old['风险等级'] == risk).sum()
        new_count = (df_new['风险等级'] == risk).sum()
        change = new_count - old_count
        change_str = f"{change:+d}" if change != 0 else "0"
        print(f"{risk:<30} {old_count:<20} {new_count:<20} {change_str}")
    
    print()
    old_delays = df_old['预测结果'].sum()
    new_delays = df_new['预测结果'].sum()
    print(f"{'Predicted delays':<30} {old_delays:<20} {new_delays:<20} {new_delays - old_delays:+d}")
    
    old_avg = df_old['延迟概率(%)'].mean()
    new_avg = df_new['延迟概率(%)'].mean()
    print(f"{'Avg delay probability':<30} {old_avg:.1f}%{'':<15} {new_avg:.1f}%{'':<15} {new_avg - old_avg:+.1f}%")
    
    # Find orders with significant changes
    print("\n\n🔍 ORDERS WITH SIGNIFICANT PROBABILITY CHANGES (>10%):")
    print("-" * 80)
    
    # Merge on production order
    merged = df_old.merge(
        df_new,
        on='生产订单',
        suffixes=('_old', '_new')
    )
    
    merged['prob_change'] = merged['延迟概率(%)_new'] - merged['延迟概率(%)_old']
    
    # Show top changes
    significant = merged[abs(merged['prob_change']) > 10].sort_values('prob_change', ascending=False)
    
    if len(significant) > 0:
        for idx, row in significant.head(10).iterrows():
            order = row['生产订单']
            mat = row['物料号_new']
            old_prob = row['延迟概率(%)_old']
            new_prob = row['延迟概率(%)_new']
            change = row['prob_change']
            old_risk = row['风险等级_old']
            new_risk = row['风险等级_new']
            
            arrow = "📈" if change > 0 else "📉"
            print(f"\n{arrow} {order}")
            print(f"   Material: {mat}")
            print(f"   Old: {old_prob:.1f}% ({old_risk}) → New: {new_prob:.1f}% ({new_risk})")
            print(f"   Change: {change:+.1f}%")
    else:
        print("No significant changes (all changes < 10%)")
    
    # Focus on high-risk orders
    print("\n\n🔴 HIGH-RISK ORDERS COMPARISON:")
    print("-" * 80)
    
    high_risk_old = set(df_old[df_old['风险等级'] == '高风险']['生产订单'])
    high_risk_new = set(df_new[df_new['风险等级'] == '高风险']['生产订单'])
    
    print(f"\nOld model high-risk: {len(high_risk_old)} orders")
    for order in high_risk_old:
        row = df_old[df_old['生产订单'] == order].iloc[0]
        print(f"  • {order}: {row['延迟概率(%)']}% - {row['物料号']}")
    
    print(f"\nNew model high-risk: {len(high_risk_new)} orders")
    for order in high_risk_new:
        row = df_new[df_new['生产订单'] == order].iloc[0]
        print(f"  • {order}: {row['延迟概率(%)']}% - {row['物料号']}")
    
    # Check if same orders
    same = high_risk_old == high_risk_new
    if same:
        print("\n✅ Same high-risk orders identified by both models")
    else:
        only_old = high_risk_old - high_risk_new
        only_new = high_risk_new - high_risk_old
        
        if only_old:
            print(f"\n⚠️  Only in old model ({len(only_old)}): {only_old}")
        if only_new:
            print(f"\n⚠️  Only in new model ({len(only_new)}): {only_new}")
    
    print("\n" + "=" * 80)
    
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
