"""
Train XGBoost model for production time prediction (regression)
Predicts: total production time = Actual finish date - Created on

v4: Huber loss, log-transform, SMAPE, winsorized target, richer features, optional Optuna
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.production_time_feature_engineer import ProductionTimeFeatureEngineer
from src.models.production_time_model import ProductionTimeModel
from loguru import logger
import pandas as pd
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────
USE_OPTUNA = False      # Set True to run Optuna hyperparameter search first
OPTUNA_TRIALS = 50     # Number of Optuna trials when USE_OPTUNA=True
LOG_TRANSFORM = False  # v4: disabled – target is winsorized [1,14], log compresses useful range
# ───────────────────────────────────────────────────────────────────────────


def main():
    """Main training pipeline for production time prediction (v3)"""

    logger.info("=" * 70)
    logger.info("PRODUCTION TIME PREDICTION MODEL TRAINING (v3)")
    logger.info("=" * 70)
    
    # Step 1: Load data
    logger.info("\n📁 Step 1: Loading data...")
    data_loader = APSDataLoader(data_dir="data/raw")
    
    df = data_loader.load_and_merge()
    logger.info(f"✓ Loaded {len(df)} production orders")
    
    # Step 2: Feature engineering (v2 with all improvements)
    logger.info("\n🔧 Step 2: Feature engineering (v2)...")
    feature_engineer = ProductionTimeFeatureEngineer(lookback_days=90)
    df_featured = feature_engineer.transform(df)
    
    logger.info(f"✓ Feature engineering complete. Shape: {df_featured.shape}")
    
    # Step 3: Prepare features and target
    # Data is already sorted by created_date from feature engineering
    logger.info("\n📊 Step 3: Preparing features and target...")
    feature_cols = feature_engineer.get_feature_columns(df_featured)
    
    X = df_featured[feature_cols].copy()
    y = df_featured['actual_production_days'].copy()

    # v4: Feature selection — drop near-zero-variance and low-importance features to reduce overfitting
    # Keep only features with non-trivial variance
    from sklearn.feature_selection import VarianceThreshold
    var_sel = VarianceThreshold(threshold=0.01)
    var_sel.fit(X)
    kept_cols = [c for c, keep in zip(X.columns, var_sel.get_support()) if keep]
    dropped_var = len(X.columns) - len(kept_cols)
    if dropped_var:
        logger.info(f"  Dropped {dropped_var} near-zero-variance features")
    X = X[kept_cols]
    feature_cols = kept_cols
    
    # Prepare metadata for predictions (material info, order info, etc.)
    metadata_cols = [
        'production_number', 'material', 'material_description',
        'order_quantity', 'production_line',
        'planned_start_date', 'planned_finish_date',
        'sales_doc', 'item'
    ]
    # Only include columns that exist
    existing_metadata_cols = [col for col in metadata_cols if col in df_featured.columns]
    metadata_df = df_featured[existing_metadata_cols].copy()
    
    logger.info(f"Features: {len(feature_cols)}")
    logger.info(f"Samples: {len(X)}")
    logger.info(f"Metadata columns: {len(existing_metadata_cols)}")
    logger.info(f"Target variable: actual_production_days")
    logger.info(f"  Range: {y.min():.2f} - {y.max():.2f} days")
    logger.info(f"  Mean: {y.mean():.2f} days")
    logger.info(f"  Median: {y.median():.2f} days")
    
    # Step 4: Train model
    logger.info("\n🤖 Step 4: Training XGBoost regression model...")

    model_params = {
        "objective": "reg:pseudohubererror",
        "huber_slope": 2.0,
        "eval_metric": ["rmse", "mae"],
        "max_depth": 4,
        "min_child_weight": 10,
        "subsample": 0.7,
        "colsample_bytree": 0.5,
        "gamma": 0.5,
        "reg_alpha": 1.0,
        "reg_lambda": 5.0,
        "learning_rate": 0.03,
        "n_estimators": 500,
        "random_state": 42,
        "n_jobs": -1,
        "early_stopping_rounds": 30,
    }

    model = ProductionTimeModel(model_params=model_params, log_transform=LOG_TRANSFORM)

    # P2: Optional Optuna hyperparameter search (replaces default params)
    if USE_OPTUNA:
        logger.info(f"\n🔍 Running Optuna search ({OPTUNA_TRIALS} trials)...")
        best_params = model.optimize_hyperparams(X, y, n_trials=OPTUNA_TRIALS, n_splits=3)
        logger.info(f"✓ Optuna complete. Best params: {best_params}")

    metrics, predictions_df = model.train(
        X, y,
        test_size=0.2,
        random_state=42,
        metadata_df=metadata_df
    )
    
    # Step 5: Feature importance
    logger.info("\n📊 Step 5: Feature importance analysis...")
    importance_df = model.get_feature_importance(top_n=15)
    
    logger.info("\n🔝 Top 15 Most Important Features:")
    logger.info("-" * 60)
    for idx, row in importance_df.iterrows():
        logger.info(f"  {row['feature']:45s} {row['importance']:.4f}")
    logger.info("-" * 60)
    
    # Step 6: Save model
    logger.info("\n💾 Step 6: Saving model...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    
    # Save with timestamp
    model_path = model_dir / f"production_time_model_{timestamp}.json"
    model.save(str(model_path))
    
    # Save as latest
    latest_path = model_dir / "production_time_model_latest.json"
    model.save(str(latest_path))
    
    # Step 7: Save predictions and metrics
    logger.info("\n💾 Step 7: Saving predictions and metrics...")
    
    # Save predictions
    predictions_dir = Path("predictions")
    predictions_dir.mkdir(exist_ok=True)
    
    predictions_path = predictions_dir / f"production_time_predictions_{timestamp}.csv"
    predictions_df.to_csv(predictions_path, index=False)
    logger.info(f"✓ Predictions saved to {predictions_path}")
    
    # Save feature importance
    importance_path = predictions_dir / f"production_time_feature_importance_{timestamp}.csv"
    importance_df.to_csv(importance_path, index=False)
    logger.info(f"✓ Feature importance saved to {importance_path}")
    
    # Save metrics (including CV)
    metrics_to_save = {**metrics}
    if model.cv_metrics:
        metrics_to_save.update(model.cv_metrics)
    metrics_df = pd.DataFrame([metrics_to_save])
    metrics_path = predictions_dir / f"production_time_metrics_{timestamp}.csv"
    metrics_df.to_csv(metrics_path, index=False)
    logger.info(f"✓ Metrics saved to {metrics_path}")
    
    # Step 8: Summary
    logger.info("\n" + "=" * 70)
    logger.info("✅ TRAINING COMPLETE (v2)")
    logger.info("=" * 70)
    logger.info(f"\n📊 Model Performance Summary (time-series split):")
    logger.info(f"  Test RMSE:  {metrics['test_rmse']:.3f} days")
    logger.info(f"  Test MAE:   {metrics['test_mae']:.3f} days")
    logger.info(f"  Test R²:    {metrics['test_r2']:.4f}")
    logger.info(f"  Test SMAPE: {metrics['test_smape']:.2f}%")
    if model.cv_metrics:
        logger.info(f"\n📊 Cross-Validation (5-fold TimeSeriesCV):")
        logger.info(f"  CV RMSE:  {model.cv_metrics['cv_rmse_mean']:.3f} ± {model.cv_metrics['cv_rmse_std']:.3f}")
        logger.info(f"  CV MAE:   {model.cv_metrics['cv_mae_mean']:.3f} ± {model.cv_metrics['cv_mae_std']:.3f}")
        logger.info(f"  CV R²:    {model.cv_metrics['cv_r2_mean']:.4f} ± {model.cv_metrics['cv_r2_std']:.4f}")
    
    logger.info(f"\n💾 Saved Files:")
    logger.info(f"  Model:       {latest_path}")
    logger.info(f"  Predictions: {predictions_path}")
    logger.info(f"  Importance:  {importance_path}")
    logger.info(f"  Metrics:     {metrics_path}")
    
    logger.info("\n🎯 Next Steps:")
    logger.info("  1. Review predictions: predictions/production_time_predictions_*.csv")
    logger.info("  2. Use model for new predictions")
    logger.info("  3. Compare with delay prediction model results")
    
    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    main()
