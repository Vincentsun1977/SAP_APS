import sys
from pathlib import Path

import pandas as pd
import sys
sys.path.append('.')

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer
from src.models.xgboost_model import ProductionDelayModel


def load_latest_model():
    import glob
    model_files = glob.glob("models/aps_xgb_model_*.pkl")
    if not model_files:
        print("No model found in models/")
        return None, None
    latest = max(model_files)
    model = ProductionDelayModel()
    model.load(latest)
    model.feature_names = APSFeatureEngineer().get_feature_names()
    return model, latest


def main(order_prefix: str = "504556134"):
    model, model_path = load_latest_model()
    if model is None:
        return 2

    # Prepare data
    input_file = Path('data/raw/prediction_input.csv')
    df_new = pd.read_csv(input_file)

    loader = APSDataLoader(data_dir='data/raw')
    df_history = loader.load_and_merge()

    # Standardize column names as in predict script
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

    # convert dates
    df_new['planned_start_date'] = pd.to_datetime(df_new['planned_start_date'], errors='coerce')
    df_new['planned_finish_date'] = pd.to_datetime(df_new['planned_finish_date'], errors='coerce')

    # Merge FG and Capacity if needed (APS loader will handle history merges)
    # Combine
    df_combined = pd.concat([df_history, df_new], ignore_index=True)
    df_combined = df_combined.sort_values('planned_start_date')

    engineer = APSFeatureEngineer(lookback_days=90)
    df_features = engineer.transform(df_combined)

    # extract new orders' features
    df_new_features = df_features.tail(len(df_new)).reset_index(drop=True)
    df_new_original = df_new.reset_index(drop=True)

    # find matching row
    mask = (
        df_new_original['sales_doc'].astype(str).str.startswith(order_prefix)
    ) | (
        df_new_original['production_number'].astype(str).str.startswith(order_prefix)
    )
    if not mask.any():
        print(f"No matching rows for {order_prefix}")
        return 1

    idx = df_new_original[mask].index[0]

    features = model.feature_names
    fv = df_new_features.loc[idx, features]

    print("Production number:", df_new_original.loc[idx, 'production_number'])
    print("Material:", df_new_original.loc[idx, 'material'])
    # If delay_probability exists
    if 'delay_probability' in df_new_features.columns:
        print("Model delay_probability (if present):", df_new_features.loc[idx, 'delay_probability'])

    # Feature importances
    try:
        fi = model.model.feature_importances_
        imp = list(zip(features, fi))
        imp = sorted(imp, key=lambda x: x[1], reverse=True)[:15]
        print('\nTop feature importances:')
        for f, v in imp:
            print(f"  {f}: {v:.4f}")
    except Exception as e:
        print('Could not read feature importances:', e)

    print('\nFeature values for this order (top positive values):')
    print(fv.sort_values(ascending=False).head(30))

    return 0


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else '504556134'
    raise SystemExit(main(arg))
