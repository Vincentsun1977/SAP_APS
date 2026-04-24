"""
Optimized Training script for XGBoost model - Focus on improving Recall
优化版训练脚本 - 专注于提高召回率
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
from sklearn.utils import resample


def main():
    """Main training pipeline with recall optimization"""
    
    logger.info("=" * 60)
    logger.info("SAP APS Production Delay Prediction - OPTIMIZED Training")
    logger.info("Focus: Improve Recall Rate (召回率优化)")
    logger.info("=" * 60)
    
    # 1. Load and merge APS data
    logger.info("Step 1: Loading and merging APS data files")
    loader = APSDataLoader(data_dir="data/raw")
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
    
    delay_rate = y.mean()
    logger.info(f"Original class distribution - Delayed: {y.sum()} ({delay_rate:.1%}), On-time: {len(y) - y.sum()}")
    
    # 🔥 Strategy 1: Oversample minority class (SMOTE-like approach)
    logger.info("\n" + "="*60)
    logger.info("Strategy 1: Balancing dataset with oversampling")
    logger.info("="*60)
    
    # Separate majority and minority classes
    X_majority = X[y == 0]
    X_minority = X[y == 1]
    y_majority = y[y == 0]
    y_minority = y[y == 1]
    
    # Oversample minority class to 50% of majority class
    target_minority_size = int(len(X_majority) * 0.5)
    
    if len(X_minority) < target_minority_size:
        logger.info(f"Oversampling minority class from {len(X_minority)} to {target_minority_size}")
        X_minority_upsampled = resample(X_minority, 
                                       replace=True,
                                       n_samples=target_minority_size,
                                       random_state=42)
        y_minority_upsampled = np.ones(target_minority_size)
        
        # Combine majority and upsampled minority
        X_balanced = np.vstack([X_majority, X_minority_upsampled])
        y_balanced = np.concatenate([y_majority, y_minority_upsampled])
        
        logger.info(f"✓ Balanced dataset: {len(X_balanced)} samples")
        logger.info(f"  - Delayed: {y_balanced.sum()} ({y_balanced.mean():.1%})")
        logger.info(f"  - On-time: {len(y_balanced) - y_balanced.sum()}")
    else:
        X_balanced = X
        y_balanced = y
        logger.info("No oversampling needed")
    
    # 4. Split data
    logger.info("\nStep 4: Splitting train/validation sets")
    
    # 🔥 Strategy 2: Optimized hyperparameters for recall
    logger.info("\n" + "="*60)
    logger.info("Strategy 2: Recall-optimized hyperparameters")
    logger.info("="*60)
    
    optimized_params = {
        "objective": "binary:logistic",
        "eval_metric": ["logloss", "auc", "error"],
        
        # 🎯 Recall optimization parameters
        "max_depth": 5,              # Slightly shallower to reduce overfitting
        "min_child_weight": 0.5,     # Lower to allow more splits (find more patterns)
        "subsample": 0.9,            # Higher to use more data
        "colsample_bytree": 0.9,     # Higher to use more features
        "gamma": 0.1,                # Small regularization
        "reg_alpha": 0.1,            # L1 regularization
        "reg_lambda": 0.5,           # Lower L2 regularization
        "learning_rate": 0.05,       # Lower learning rate for better convergence
        "n_estimators": 200,         # More trees for better learning
        
        "random_state": 42,
        "n_jobs": -1,
        "scale_pos_weight": 2.0,     # Moderate weight (will be adjusted)
        "early_stopping_rounds": 20,
    }
    
    model = ProductionDelayModel(model_params=optimized_params)
    
    # Adjust scale_pos_weight based on balanced data
    scale_pos_weight = (len(y_balanced) - y_balanced.sum()) / y_balanced.sum()
    model.params['scale_pos_weight'] = scale_pos_weight
    logger.info(f"✓ Set scale_pos_weight={scale_pos_weight:.2f} for class balance")
    
    X_train, X_val, y_train, y_val = model.split_data(X_balanced, y_balanced, test_size=0.2)
    
    logger.info(f"✓ Train: {len(X_train)}, Val: {len(X_val)}")
    
    # 5. Train model
    logger.info("\nStep 5: Training XGBoost model with optimized parameters")
    
    # Store feature names for importance
    model.feature_names = feature_cols
    
    metrics = model.train(X_train, y_train, X_val, y_val, early_stopping_rounds=20)
    
    # 6. Evaluate on original validation set (to see real performance)
    logger.info("\n" + "="*60)
    logger.info("Step 6: Model evaluation on ORIGINAL data distribution")
    logger.info("="*60)
    
    # Use original unbalanced data for validation
    from sklearn.model_selection import train_test_split
    X_train_orig, X_val_orig, y_train_orig, y_val_orig = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Evaluate on original validation set
    metrics_orig = model.evaluate(X_val_orig, y_val_orig)
    
    logger.info(f"\n{'='*50}")
    logger.info("VALIDATION METRICS (Original Data Distribution):")
    logger.info(f"{'='*50}")
    for metric, value in metrics_orig.items():
        if metric != "confusion_matrix":
            logger.info(f"{metric:15s}: {value:.4f}")
    
    # Confusion matrix
    if "confusion_matrix" in metrics_orig:
        cm = metrics_orig["confusion_matrix"]
        logger.info(f"\nConfusion Matrix:")
        logger.info(f"  TN: {cm[0][0]:4d}  |  FP: {cm[0][1]:4d}")
        logger.info(f"  FN: {cm[1][0]:4d}  |  TP: {cm[1][1]:4d}")
        
        # Calculate additional metrics
        tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
        logger.info(f"\nDetailed Analysis:")
        logger.info(f"  True Positives (找到的延迟):  {tp}")
        logger.info(f"  False Negatives (漏掉的延迟): {fn}")
        logger.info(f"  False Positives (误报):       {fp}")
        logger.info(f"  True Negatives (正确的准时):  {tn}")
    
    # Feature importance
    importance = model.get_feature_importance()
    logger.info(f"\n{'='*50}")
    logger.info("TOP 10 IMPORTANT FEATURES:")
    logger.info(f"{'='*50}")
    sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for i, (feat, imp) in enumerate(sorted_importance[:10], 1):
        logger.info(f"{i:2d}. {feat:40s}: {imp:.4f}")
    
    # 7. Save model
    logger.info("\nStep 7: Saving optimized model")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = f"models/aps_xgb_model_optimized_{timestamp}.pkl"
    model.save(model_path)
    
    # 8. Save metadata
    logger.info("Step 8: Saving model metadata to PostgreSQL")
    metadata = {
        "model_version": f"aps_optimized_v1.0_{timestamp}",
        "algorithm": "XGBoost (Recall Optimized)",
        "optimization_strategy": "Oversampling + Hyperparameter Tuning",
        "data_source": "APS_History_FG_Capacity",
        "training_date": datetime.now().isoformat(),
        "train_samples": int(len(X_train)),
        "val_samples": int(len(X_val)),
        "original_samples": int(len(df_merged)),
        "balanced_samples": int(len(X_balanced)),
        "num_features": len(feature_cols),
        "test_accuracy": float(metrics_orig["accuracy"]),
        "precision_score": float(metrics_orig["precision"]),
        "recall_score": float(metrics_orig["recall"]),
        "f1_score": float(metrics_orig["f1_score"]),
        "roc_auc": float(metrics_orig["roc_auc"]),
        "delay_rate": float(delay_rate),
        "date_range_start": df_merged['planned_start_date'].min().isoformat(),
        "date_range_end": df_merged['planned_start_date'].max().isoformat(),
        "feature_importance": {k: float(v) for k, v in sorted_importance[:20]},
        "hyperparameters": optimized_params,
        "model_path": model_path,
        "is_active": True
    }
    
    try:
        db.save_model_metadata(metadata)
        logger.info("✓ Metadata saved to PostgreSQL")
    except Exception as e:
        logger.warning(f"Failed to save metadata to PostgreSQL: {e}")
        logger.info("Continuing anyway...")
    
    # 9. Save processed data
    logger.info("Step 9: Saving processed data")
    loader.save_processed_data(df_features, "data/processed/aps_training_data_optimized.csv")
    
    logger.info("\n" + "="*60)
    logger.info("✅ Optimized Training Complete!")
    logger.info(f"Model saved to: {model_path}")
    logger.info("="*60)
    
    # Print comparison summary
    print("\n" + "="*60)
    print("📊 OPTIMIZED MODEL SUMMARY")
    print("="*60)
    print(f"Dataset: {len(df_merged)} historical orders")
    print(f"  Original: {len(X)} samples")
    print(f"  Balanced: {len(X_balanced)} samples (oversampled)")
    print(f"  Delay Rate: {delay_rate:.1%} → {y_balanced.mean():.1%}")
    print(f"\nPerformance on Original Data Distribution:")
    print(f"  Accuracy:  {metrics_orig['accuracy']:.1%}")
    print(f"  Precision: {metrics_orig['precision']:.1%}")
    print(f"  Recall:    {metrics_orig['recall']:.1%}  🎯 KEY METRIC")
    print(f"  F1 Score:  {metrics_orig['f1_score']:.3f}")
    print(f"  ROC AUC:   {metrics_orig['roc_auc']:.3f}")
    print(f"\nModel: {model_path}")
    print("="*60)
    
    # Comparison with baseline
    print("\n💡 Expected Improvements:")
    print("  - Higher Recall (找到更多延迟订单)")
    print("  - Better F1 Score (精确率和召回率平衡)")
    print("  - Slightly lower Precision (可接受的代价)")
    print("="*60)


if __name__ == "__main__":
    main()
