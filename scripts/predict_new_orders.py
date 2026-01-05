"""
Predict delay risk for new production orders
预测新生产订单的延迟风险
"""
import sys
sys.path.append('.')

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from loguru import logger
import argparse
import glob

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer
from src.models.xgboost_model import ProductionDelayModel


def load_latest_model():
    """Load the latest trained model"""
    # Find latest model file
    model_files = glob.glob("models/aps_xgb_model_*.pkl")
    
    if not model_files:
        logger.error("No trained model found in models/ directory")
        logger.info("Please run: python scripts/train_aps_model.py first")
        return None
    
    latest_model = max(model_files)
    logger.info(f"Loading model: {latest_model}")
    
    model = ProductionDelayModel()
    model.load(latest_model)
    
    # Set feature names
    engineer = APSFeatureEngineer()
    model.feature_names = engineer.get_feature_names()
    
    logger.info(f"✓ Model loaded successfully")
    return model, latest_model


def prepare_prediction_data(input_file: str, history_file: str = "data/raw/History.csv"):
    """
    Prepare new orders for prediction
    
    Args:
        input_file: Path to new orders CSV file
        history_file: Path to historical data (for historical features)
    
    Returns:
        DataFrame with engineered features
    """
    logger.info(f"Loading new orders from: {input_file}")
    
    # Load new orders
    df_new = pd.read_csv(input_file)
    logger.info(f"✓ Loaded {len(df_new)} new orders")
    
    # Load historical data for feature engineering
    loader = APSDataLoader(data_dir="data/raw")
    df_history = loader.load_and_merge()
    
    logger.info(f"✓ Loaded {len(df_history)} historical orders for feature calculation")
    
    # Standardize column names for new orders
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
    df_new['planned_start_date'] = pd.to_datetime(df_new['planned_start_date'], errors='coerce')
    df_new['planned_finish_date'] = pd.to_datetime(df_new['planned_finish_date'], errors='coerce')
    
    # Merge with FG and Capacity data if not already present
    if 'total_production_time' not in df_new.columns:
        fg_df = pd.read_csv("data/raw/FG.csv")
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
        capacity_df = pd.read_csv("data/raw/Capacity.csv")
        df_new = df_new.merge(
            capacity_df[['Production Line', 'Capacity']],
            left_on='production_line',
            right_on='Production Line',
            how='left',
            suffixes=('', '_cap')
        )
        df_new['line_capacity'] = df_new['Capacity']
    
    # Create basic features (same as in loader)
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
    
    # Combine with history for feature engineering
    df_combined = pd.concat([df_history, df_new], ignore_index=True)
    df_combined = df_combined.sort_values('planned_start_date')
    
    # Apply feature engineering
    logger.info("Engineering features...")
    engineer = APSFeatureEngineer(lookback_days=90)
    df_features = engineer.transform(df_combined)
    
    # Extract only the new orders
    df_new_features = df_features.tail(len(df_new)).copy()
    
    logger.info(f"✓ Feature engineering complete")
    
    return df_new_features, df_new


def predict_orders(model, df_features, feature_cols):
    """
    Make predictions on new orders
    
    Args:
        model: Trained model
        df_features: DataFrame with features
        feature_cols: List of feature column names
    
    Returns:
        DataFrame with predictions
    """
    logger.info("Making predictions...")
    
    # Select features
    # Ensure no missing or non-numeric values are passed to the model
    missing_before = df_features[feature_cols].isna().sum().sum()
    if missing_before > 0:
        logger.warning(f"Found {missing_before} missing feature values — filling with 0 for prediction")
    df_features[feature_cols] = df_features[feature_cols].fillna(0)
    X = df_features[feature_cols].values
    
    # Predict
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    
    # Add to dataframe
    df_features['delay_probability'] = probabilities[:, 1]
    df_features['predicted_delay'] = predictions
    
    # Risk level
    df_features['risk_level'] = pd.cut(
        df_features['delay_probability'],
        bins=[0, 0.3, 0.7, 1.0],
        labels=['低风险', '中风险', '高风险']
    )
    
    logger.info(f"✓ Predictions complete")
    logger.info(f"  - 高风险: {(df_features['risk_level'] == '高风险').sum()}")
    logger.info(f"  - 中风险: {(df_features['risk_level'] == '中风险').sum()}")
    logger.info(f"  - 低风险: {(df_features['risk_level'] == '低风险').sum()}")
    
    return df_features


def save_predictions(df_predictions, df_original, output_file):
    """
    Save prediction results
    
    Args:
        df_predictions: DataFrame with predictions and features
        df_original: Original input data
        output_file: Output file path
    """
    # Select key columns for output
    output_cols = [
        'sales_doc', 'item', 'production_number', 'material', 'material_description',
        'order_quantity', 'planned_start_date', 'planned_finish_date',
        'production_line', 'delay_probability', 'predicted_delay', 'risk_level'
    ]
    
    # Filter available columns
    available_cols = [col for col in output_cols if col in df_predictions.columns]
    df_output = df_predictions[available_cols].copy()
    
    # Format dates
    if 'planned_start_date' in df_output.columns:
        df_output['planned_start_date'] = df_output['planned_start_date'].dt.strftime('%Y-%m-%d')
    if 'planned_finish_date' in df_output.columns:
        df_output['planned_finish_date'] = df_output['planned_finish_date'].dt.strftime('%Y-%m-%d')
    
    # Format probability as percentage
    df_output['delay_probability_pct'] = (df_output['delay_probability'] * 100).round(1)
    
    # Rename for clarity
    df_output = df_output.rename(columns={
        'sales_doc': '销售订单',
        'item': '行项目',
        'production_number': '生产订单',
        'material': '物料号',
        'material_description': '物料描述',
        'order_quantity': '订单数量',
        'planned_start_date': '计划开始日期',
        'planned_finish_date': '计划完成日期',
        'production_line': '生产线',
        'delay_probability': '延迟概率',
        'delay_probability_pct': '延迟概率(%)',
        'predicted_delay': '预测结果',
        'risk_level': '风险等级'
    })
    
    # Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_output.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    logger.info(f"✓ Predictions saved to: {output_file}")
    
    return df_output


def main():
    """Main prediction pipeline"""
    parser = argparse.ArgumentParser(description='Predict production order delays')
    parser.add_argument('--input', '-i', 
                       default='data/sample/new_orders_example.csv',
                       help='Input CSV file with new orders')
    parser.add_argument('--output', '-o',
                       default='predictions/predictions_latest.csv',
                       help='Output CSV file for predictions')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SAP Production Delay Prediction - New Orders")
    logger.info("=" * 60)
    
    # 1. Load model
    result = load_latest_model()
    if result is None:
        return
    
    model, model_path = result
    logger.info(f"Model: {Path(model_path).name}")
    
    # 2. Prepare data
    try:
        df_features, df_original = prepare_prediction_data(args.input)
    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input}")
        logger.info("Please create the input file or use the example:")
        logger.info("  python scripts/predict_new_orders.py --input data/sample/new_orders_example.csv")
        return
    except Exception as e:
        logger.error(f"Error preparing data: {e}")
        return
    
    # 3. Get feature columns
    feature_cols = model.feature_names or APSFeatureEngineer().get_feature_names()
    
    # 4. Make predictions
    df_predictions = predict_orders(model, df_features, feature_cols)
    
    # 5. Save results
    df_output = save_predictions(df_predictions, df_original, args.output)
    
    # 6. Print summary
    print("\n" + "=" * 60)
    print("📊 PREDICTION SUMMARY")
    print("=" * 60)
    print(f"Input file: {args.input}")
    print(f"Orders processed: {len(df_output)}")
    print(f"\nRisk Distribution:")
    print(f"  🔴 高风险: {(df_output['风险等级'] == '高风险').sum()} orders")
    print(f"  🟡 中风险: {(df_output['风险等级'] == '中风险').sum()} orders")
    print(f"  🟢 低风险: {(df_output['风险等级'] == '低风险').sum()} orders")
    print(f"\nPredicted delays: {df_output['预测结果'].sum()} / {len(df_output)}")
    print(f"Average delay probability: {df_output['延迟概率(%)'].mean():.1f}%")
    print(f"\nResults saved to: {args.output}")
    print("=" * 60)
    
    # Show top 5 high-risk orders
    high_risk = df_output[df_output['风险等级'] == '高风险'].sort_values('延迟概率(%)', ascending=False)
    if len(high_risk) > 0:
        print("\n🔴 TOP HIGH-RISK ORDERS:")
        print("-" * 60)
        for idx, row in high_risk.head(5).iterrows():
            print(f"  • {row.get('物料号', 'N/A')} - {row.get('物料描述', 'N/A')[:30]}")
            print(f"    延迟概率: {row['延迟概率(%)']}% | 订单: {row.get('生产订单', 'N/A')}")
        print("-" * 60)


if __name__ == "__main__":
    main()
