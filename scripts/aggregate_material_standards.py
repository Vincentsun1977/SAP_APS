"""
Aggregate Material Production Standards
========================================
This script aggregates predicted production times by material and production line
to create a standard production time reference table.

Usage:
    python scripts/aggregate_material_standards.py
    python scripts/aggregate_material_standards.py --input predictions/production_time_predictions_20260110_095113.csv
"""

import pandas as pd
import argparse
from pathlib import Path
import sys

def aggregate_material_standards(input_file: str, output_file: str = None):
    """
    Aggregate predicted production times by material and production line.
    
    Args:
        input_file: Path to the predictions CSV file
        output_file: Path to save the aggregated standards (optional)
    
    Returns:
        DataFrame with aggregated standards
    """
    print(f"Reading predictions from: {input_file}")
    
    # Read predictions
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    print(f"Loaded {len(df)} predictions")
    
    # Check required columns
    required_cols = ['production_line', 'material', 'material_description', 'predicted']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing required columns: {missing_cols}")
        print(f"Available columns: {df.columns.tolist()}")
        sys.exit(1)
    
    # Group by production line and material, calculate mean predicted time
    print("\nAggregating by production_line, material, and material_description...")
    standards = df.groupby(
        ['production_line', 'material', 'material_description'],
        as_index=False
    ).agg({
        'predicted': ['mean', 'std', 'min', 'max', 'count']
    })
    
    # Flatten multi-level columns
    standards.columns = [
        'production_line', 
        'material', 
        'material_description',
        'predicted_avg',
        'predicted_std',
        'predicted_min',
        'predicted_max',
        'sample_count'
    ]
    
    # Round numeric values for readability
    standards['predicted_avg'] = standards['predicted_avg'].round(4)
    standards['predicted_std'] = standards['predicted_std'].round(4)
    standards['predicted_min'] = standards['predicted_min'].round(4)
    standards['predicted_max'] = standards['predicted_max'].round(4)
    
    # Sort by production line and material
    standards = standards.sort_values(['production_line', 'material'])
    
    print(f"\nGenerated {len(standards)} material standards")
    print("\nSample of aggregated standards:")
    print(standards.head(10).to_string(index=False))
    
    # Determine output file
    if output_file is None:
        output_dir = Path(input_file).parent
        output_file = output_dir / 'material_production_standards.csv'
    
    # Save to CSV
    standards.to_csv(output_file, index=False)
    print(f"\n✓ Material standards saved to: {output_file}")
    
    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY BY PRODUCTION LINE")
    print("="*60)
    summary = standards.groupby('production_line').agg({
        'predicted_avg': ['mean', 'min', 'max'],
        'material': 'count'
    })
    summary.columns = ['avg_time', 'min_time', 'max_time', 'material_count']
    print(summary.to_string())
    
    return standards


def main():
    parser = argparse.ArgumentParser(
        description='Aggregate material production standards from predictions'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='predictions/production_time_predictions_latest.csv',
        help='Input predictions CSV file (default: production_time_predictions_latest.csv)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output standards CSV file (default: material_production_standards.csv in same directory as input)'
    )
    parser.add_argument(
        '--simple',
        action='store_true',
        help='Output only the 4 basic columns (production_line, material_description, material, predicted_avg)'
    )
    
    args = parser.parse_args()
    
    # Aggregate standards
    standards = aggregate_material_standards(args.input, args.output)
    
    # If simple mode, create a simplified version
    if args.simple:
        simple_standards = standards[['production_line', 'material_description', 'material', 'predicted_avg']]
        simple_output = str(args.output or 'predictions/material_production_standards.csv').replace('.csv', '_simple.csv')
        simple_standards.to_csv(simple_output, index=False)
        print(f"\n✓ Simplified standards saved to: {simple_output}")
        print("\nSimplified output columns: production_line, material_description, material, predicted_avg")


if __name__ == '__main__':
    main()
