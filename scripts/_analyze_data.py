"""Temporary script to analyze data coverage and label distribution"""
import pandas as pd
import numpy as np

h = pd.read_csv('data/raw/History.csv')
print(f'Total History rows: {len(h)}')
h['afd'] = pd.to_datetime(h['Actual finish date'], errors='coerce')
n_valid = h['afd'].notna().sum()
print(f'Rows with actual finish: {n_valid}')
print(f'Unique materials: {h["Material Number"].nunique()}')
print(f'Unique MRP controllers: {h["MRP controller"].nunique()}')

fg = pd.read_csv('data/raw/FG.csv')
print(f'\n=== FG.csv ===')
print(f'Rows: {len(fg)}, Columns: {list(fg.columns)}')

sh = pd.read_csv('data/raw/Shortage.csv')
print(f'\n=== Shortage.csv ===')
print(f'Rows: {len(sh)}, Columns: {list(sh.columns)}')

cap = pd.read_csv('data/raw/Capacity.csv')
print(f'\n=== Capacity.csv ===')
print(f'Rows: {len(cap)}, Columns: {list(cap.columns)}')

# FG join overlap
fg_materials = set(fg.iloc[:, 0].astype(str).values)
hist_materials = set(h['Material Number'].astype(str).values)
overlap = fg_materials & hist_materials
print(f'\n=== FG join check ===')
print(f'FG materials: {len(fg_materials)}')
print(f'History materials: {len(hist_materials)}')
print(f'Overlap: {len(overlap)}')
print(f'History rows with FG match: {h["Material Number"].astype(str).isin(fg_materials).sum()}')

# Check label distribution for 1-day orders (MAPE issue)
h['created_date'] = pd.to_datetime(h['Created on'], errors='coerce')
valid = h.dropna(subset=['afd', 'created_date'])
days = (valid['afd'] - valid['created_date']).dt.total_seconds() / (24 * 3600)
days_clamped = np.maximum(days, 1.0)
mask = (days_clamped <= 30) & (valid['Order quantity (GMEIN)'] <= 500)
days_clean = days_clamped[mask]

print(f'\n=== Label stats after filters ===')
print(f'Count: {len(days_clean)}')
# Fraction near 1 day (small denominators inflate MAPE)
pct_le1 = (days_clean <= 1.0).mean() * 100
pct_le2 = (days_clean <= 2.0).mean() * 100
print(f'% with <=1 day: {pct_le1:.1f}%')
print(f'% with <=2 days: {pct_le2:.1f}%')

# Coefficient of variation
cv = days_clean.std() / days_clean.mean()
print(f'Coefficient of variation: {cv:.3f}')
print(f'This means the data has HIGH natural variability relative to mean')
