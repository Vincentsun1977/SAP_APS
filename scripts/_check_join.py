"""Check material column matching between FG and History"""
import pandas as pd

fg = pd.read_csv('data/raw/FG.csv')
print('FG Material samples:')
print(fg['Material'].head(20).tolist())
print(f'FG Material dtype: {fg["Material"].dtype}')
print(f'FG Material unique count: {fg["Material"].nunique()}')

h = pd.read_csv('data/raw/History.csv')
print('\nHistory Material samples:')
print(h['Material Number'].head(20).tolist())
print(f'History Material dtype: {h["Material Number"].dtype}')

# Try string matching
fg_set = set(fg['Material'].astype(str).str.strip().values)
h_set = set(h['Material Number'].astype(str).str.strip().values)
print(f'\nFG set: {fg_set}')
print(f'\nOverlap after strip: {fg_set & h_set}')

# Check merge after column rename (as in aps_data_loader)
fg2 = fg.copy()
fg2.columns = fg2.columns.str.strip()
fg2 = fg2.rename(columns={'Material': 'material'})

h2 = h.copy()
h2 = h2.rename(columns={'Material Number': 'material'})

merged = h2.merge(fg2[['material']], on='material', how='inner')
print(f'\nInner merge rows: {len(merged)}')

# left join - count non-null
merged_left = h2.merge(fg2[['material', 'Constraint']], on='material', how='left')
print(f'Left join - with FG match: {merged_left["Constraint"].notna().sum()} / {len(merged_left)}')
