"""
Training script for XGBoost model using APS data
Updated to work with new data structure: History, Order, FG, Capacity, APS
"""
import sys
sys.path.append('.')

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer
from src.models.xgboost_model import ProductionDelayModel
from src.database.connection import db
from loguru import logger
import pandas as pd
import numpy as np
from datetime import datetime


def main():
    """Main training pipeline for APS production delay prediction"""
    
    logger.info("=" * 60)
    logger.info("SAP APS Production Delay Prediction - Model Training")
    logger.info("=" * 60)
    
    # 1. Load and merge APS data
    logger.info("Step 1: Loading and merging APS data files")
    loader =APSDataLoader(data_dir="data/raw")
    df_merged = loader.load_and_merge()
    
    # Validate merged data
    is_valid, errors = loader.validate_data(df_merged)
    if not is_valid:
        logger.error(f"Data validation failed: {errors}")
        return
    
    logger.info(f"✓ Loaded {len(df_merged)} historical production orders")
    logger.info(f"✓ Date range: {df_merged['planned_start_date'].min()} to {df_merged['planned_start_date'].max()}")
    
    # 2. Feature engineering
    logger.info("Step 2: Engineering features")
    engineer = APSFeatureEngineer(lookback_days=90)
    df_features = engineer.transform(df_merged)
    
    # 3. Prepare training data
    logger.info("Step 3: Preparing training data")
    
    # Get feature columns
    feature_cols = engineer.get_feature_names()
    
    # Select features and handle missing values
    df_train = df_features[feature_cols + ['is_delayed']].copy()
    
    # Drop rows with missing features or targets
    initial_count = len(df_train)
    df_train = df_train.dropna()
    dropped_count = initial_count - len(df_train)
    
    if dropped_count > 0:
        logger.warning(f"Dropped {dropped_count} rows with missing values")
    
    logger.info(f"Training samples after cleaning: {len(df_train)}")
    
    if len(df_train) < 50:
        logger.error("ERROR: Too few training samples. Need at least 50.")
        return
    
    # Prepare X and y
    X = df_train[feature_cols].values
    y = df_train['is_delayed'].values
    
    logger.info(f"Features: {len(feature_cols)}")
    logger.info(f"Class distribution - Delayed: {y.sum()} ({y.mean():.1%}), On-time: {len(y) - y.sum()}")
    
    # Check class balance
    delay_rate = y.mean()
    if delay_rate < 0.05 or delay_rate > 0.95:
        logger.warning(f"WARNING: Imbalanced dataset (delay rate: {delay_rate:.1%})")
    
    # 4. Split data
    logger.info("Step 4: Splitting train/validation sets")
    model = ProductionDelayModel()
    
    # Adjust scale_pos_weight for imbalanced data
    scale_pos_weight = (len(y) - y.sum()) / y.sum()
    model.params['scale_pos_weight'] = scale_pos_weight
    logger.info(f"Set scale_pos_weight={scale_pos_weight:.2f} for class imbalance")
    
    X_train, X_val, y_train, y_val = model.split_data(X, y, test_size=0.2)
    
    logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}")
    
    # 5. Train model
    logger.info("Step 5: Training XGBoost model")
    
    # Store feature names for importance
    model.feature_names = feature_cols
    
    metrics = model.train(X_train, y_train, X_val, y_val, early_stopping_rounds=10)
    
    # 6. Evaluate
    logger.info("Step 6: Model evaluation")
    logger.info(f"\n{'='*50}")
    logger.info("VALIDATION METRICS:")
    logger.info(f"{'='*50}")
    for metric, value in metrics.items():
        if metric != "confusion_matrix":
            logger.info(f"{metric:15s}: {value:.4f}")
    
    # Confusion matrix
    if "confusion_matrix" in metrics:
        cm = metrics["confusion_matrix"]
        logger.info(f"\nConfusion Matrix:")
        logger.info(f"  TN: {cm[0][0]:4d}  |  FP: {cm[0][1]:4d}")
        logger.info(f"  FN: {cm[1][0]:4d}  |  TP: {cm[1][1]:4d}")
    
    # Feature importance
    importance = model.get_feature_importance()
    logger.info(f"\n{'='*50}")
    logger.info("TOP 10 IMPORTANT FEATURES:")
    logger.info(f"{'='*50}")
    sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for i, (feat, imp) in enumerate(sorted_importance[:10], 1):
        logger.info(f"{i:2d}. {feat:40s}: {imp:.4f}")
    
    # 7. Save model
    logger.info("\nStep 7: Saving model")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = f"models/aps_xgb_model_{timestamp}.json"
    model.save(model_path)
    
    # 8. Save metadata to Supabase
    logger.info("Step 8: Saving model metadata")
    metadata = {
        "model_version": f"aps_v1.0_{timestamp}",
        "algorithm": "XGBoost",
        "data_source": "APS_History_FG_Capacity",
        "training_date": datetime.now().isoformat(),
        "train_samples": int(len(X_train)),
        "val_samples": int(len(X_val)),
        "total_samples": int(len(df_merged)),
        "num_features": len(feature_cols),
        "test_accuracy": float(metrics["accuracy"]),
        "precision_score": float(metrics["precision"]),
        "recall_score": float(metrics["recall"]),
        "f1_score": float(metrics["f1_score"]),
        "roc_auc": float(metrics["roc_auc"]),
        "delay_rate": float(delay_rate),
        "date_range_start": df_merged['planned_start_date'].min().isoformat(),
        "date_range_end": df_merged['planned_start_date'].max().isoformat(),
        "feature_importance": {k: float(v) for k, v in sorted_importance[:20]},  # Top 20
        "hyperparameters": model.params,
        "model_path": model_path,
        "is_active": True
    }
    
    try:
        db.save_model_metadata(metadata)
        logger.info("✓ Metadata saved to Supabase")
    except Exception as e:
        logger.warning(f"Failed to save metadata to Supabase: {e}")
        logger.info("Continuing anyway...")
    
    # 9. Save processed data for future use
    logger.info("Step 9: Saving processed data")
    loader.save_processed_data(df_features, "data/processed/aps_training_data_full.csv")
    
    logger.info("\n" + "="*60)
    logger.info("✅ Training complete!")
    logger.info(f"Model saved to: {model_path}")
    logger.info(f"F1 Score: {metrics['f1_score']:.4f}")
    logger.info(f"ROC AUC: {metrics['roc_auc']:.4f}")
    logger.info(f"Training samples: {len(X_train) + len(X_val)}")
    logger.info("="*60)
    
    # Print summary for user
    print("\n" + "="*60)
    print("📊 TRAINING SUMMARY")
    print("="*60)
    print(f"Dataset: {len(df_merged)} historical orders ({df_merged['planned_start_date'].min().date()} to {df_merged['planned_start_date'].max().date()})")
    print(f"Features: {len(feature_cols)}")
    print(f"Delay Rate: {delay_rate:.1%}")
    print(f"\nPerformance:")
    print(f"  Accuracy:  {metrics['accuracy']:.1%}")
    print(f"  Precision: {metrics['precision']:.1%}")
    print(f"  Recall:    {metrics['recall']:.1%}")
    print(f"  F1 Score:  {metrics['f1_score']:.3f}")
    print(f"  ROC AUC:   {metrics['roc_auc']:.3f}")
    print(f"\nModel: {model_path}")
    print("="*60)


if __name__ == "__main__":
    main()
