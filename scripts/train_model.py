"""
Training script for XGBoost model
"""
import sys
sys.path.append('.')

from src.data_collection.csv_loader import CSVLoader
from src.data_processing.feature_engineer import FeatureEngineer
from src.models.xgboost_model import ProductionDelayModel
from src.database.connection import db
from src.config.paths import RAW_DATA_DIR, MODELS_DIR
from loguru import logger
import pandas as pd
import numpy as np
from datetime import datetime


def main():
    """Main training pipeline"""
    
    logger.info("=" * 60)
    logger.info("SAP Production Delay Prediction - Model Training")
    logger.info("=" * 60)
    
    # 1. Load data
    logger.info("Step 1: Loading CSV data")
    loader = CSVLoader(data_dir=str(RAW_DATA_DIR))
    
    df = loader.load_production_orders()
    
    # Validate data
    is_valid, errors = loader.validate_orders(df)
    if not is_valid:
        logger.error(f"Data validation failed: {errors}")
        return
    
    # 2. Feature engineering
    logger.info("Step 2: Engineering features")
    engineer = FeatureEngineer(lookback_days=30)
    df_features = engineer.transform(df)
    
    # 3. Prepare training data
    logger.info("Step 3: Preparing training data")
    
    # Filter to orders with actual finish date (for training)
    df_train = df_features[df_features['actual_finish'].notna()].copy()
    
    logger.info(f"Total orders with labels: {len(df_train)}")
    
    if len(df_train) < 50:
        logger.warning("Warning: Very few training samples. Model may not perform well.")
    
    # Get feature columns
    feature_cols = engineer.get_feature_names()
    
    # Drop rows with missing features
    df_train = df_train.dropna(subset=feature_cols + ['is_delayed'])
    
    logger.info(f"Training samples after cleaning: {len(df_train)}")
    
    # Prepare X and y
    X = df_train[feature_cols].values
    y = df_train['is_delayed'].values
    
    logger.info(f"Class distribution - Delayed: {y.sum()}, On-time: {len(y) - y.sum()}")
    
    # 4. Split data
    logger.info("Step 4: Splitting train/validation sets")
    model = ProductionDelayModel()
    X_train, X_val, y_train, y_val = model.split_data(X, y, test_size=0.2)
    
    logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}")
    
    # 5. Train model
    logger.info("Step 5: Training XGBoost model")
    metrics = model.train(X_train, y_train, X_val, y_val, early_stopping_rounds=10)
    
    # 6. Evaluate
    logger.info("Step 6: Model evaluation")
    logger.info(f"\\n{'='*50}")
    logger.info("VALIDATION METRICS:")
    logger.info(f"{'='*50}")
    for metric, value in metrics.items():
        if metric != "confusion_matrix":
            logger.info(f"{metric:15s}: {value:.4f}")
    
    # Feature importance
    importance = model.get_feature_importance()
    logger.info(f"\\n{'='*50}")
    logger.info("TOP 5 IMPORTANT FEATURES:")
    logger.info(f"{'='*50}")
    sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for feat, imp in sorted_importance[:5]:
        logger.info(f"{feat:30s}: {imp:.4f}")
    
    # 7. Save model
    logger.info("Step 7: Saving model")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = MODELS_DIR / f"xgb_model_{timestamp}.json"
    model.save(str(model_path))
    
    # 8. Save metadata to Supabase
    logger.info("Step 8: Saving model metadata")
    metadata = {
        "model_version": f"v1.0_{timestamp}",
        "algorithm": "XGBoost",
        "training_date": datetime.now().isoformat(),
        "train_samples": int(len(X_train)),
        "test_accuracy": metrics["accuracy"],
        "precision_score": metrics["precision"],
        "recall_score": metrics["recall"],
        "f1_score": metrics["f1_score"],
        "feature_importance": importance,
        "hyperparameters": model.params,
        "model_path": str(model_path),
        "is_active": True  # Mark as active model
    }
    
    try:
        db.save_model_metadata(metadata)
        logger.info("Metadata saved to Supabase")
    except Exception as e:
        logger.warning(f"Failed to save metadata to Supabase: {e}")
    
    logger.info("\\n" + "="*60)
    logger.info("✅ Training complete!")
    logger.info(f"Model saved to: {model_path}")
    logger.info(f"F1 Score: {metrics['f1_score']:.4f}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
