"""
Convert Excel files to CSV format for model training
Converts all Excel files in data/raw/ directory to CSV format
"""
import pandas as pd
import os
from pathlib import Path

def convert_excel_to_csv(data_dir="data/raw"):
    """Convert all Excel files in the directory to CSV"""
    
    data_path = Path(data_dir)
    
    # Find all Excel files
    excel_files = list(data_path.glob("*.xlsx")) + list(data_path.glob("*.XLSX"))
    
    if not excel_files:
        print(f"❌ No Excel files found in {data_dir}")
        return
    
    print(f"📁 Found {len(excel_files)} Excel files to convert:")
    print("-" * 60)
    
    for excel_file in excel_files:
        try:
            # Read Excel file
            print(f"\n📖 Reading: {excel_file.name}")
            df = pd.read_excel(excel_file)
            
            # Create CSV filename (same name, different extension)
            csv_file = excel_file.with_suffix('.csv')
            
            # Save as CSV
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            
            print(f"   ✅ Converted to: {csv_file.name}")
            print(f"   📊 Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            print(f"   📋 Columns: {', '.join(df.columns[:5].tolist())}" + 
                  (f"... (+{len(df.columns)-5} more)" if len(df.columns) > 5 else ""))
            
        except Exception as e:
            print(f"   ❌ Error converting {excel_file.name}: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✨ Conversion complete!")
    print("=" * 60)

if __name__ == "__main__":
    convert_excel_to_csv()
