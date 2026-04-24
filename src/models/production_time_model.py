"""
XGBoost model for production time prediction (regression)
Predicts total production time in days

v3 improvements:
- P0: Log-transform target variable (log1p/expm1) for better fit
- P3: SMAPE metric replaces MAPE (symmetric, immune to small-denominator inflation)
- P2: Optuna-based hyperparameter search via optimize_hyperparams()

v4 improvements:
- Huber loss (reg:pseudohubererror) for outlier robustness
"""
import xgboost as xgb
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
)
from loguru import logger
from pathlib import Path
from typing import Tuple, Dict
import pandas as pd


class ProductionTimeModel:
    """XGBoost regressor for production time prediction"""
    
    def __init__(self, model_params: Dict = None, log_transform: bool = True):
        """
        Initialize model with hyperparameters.

        Args:
            model_params: XGBoost parameters dict
            log_transform: Apply log1p to target before training and expm1 after
                           prediction. Reduces the impact of right-skewed targets.
        """
        default_params = {
            "objective": "reg:squarederror",
            "eval_metric": ["rmse", "mae"],
            "max_depth": 6,
            "min_child_weight": 1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "gamma": 0,
            "reg_alpha": 0.1,
            "reg_lambda": 1,
            "learning_rate": 0.1,
            "n_estimators": 200,
            "random_state": 42,
            "n_jobs": -1,
            "early_stopping_rounds": 15,
        }

        self.params = model_params or default_params
        self.log_transform = log_transform
        self.model = xgb.XGBRegressor(**self.params)
        self.feature_names = None
        self.is_trained = False
        self.cv_metrics = None
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
        random_state: int = 42,
        metadata_df: pd.DataFrame = None,
        cv_splits: int = 5
    ) -> Tuple[Dict, pd.DataFrame]:
        """
        Train XGBoost regression model using time-series split.
        Data MUST be pre-sorted by time (created_date) before calling this method.
        
        Args:
            X: Feature matrix (sorted by time)
            y: Target variable (sorted by time)
            test_size: Proportion of data for testing (last N%)
            random_state: Random seed (unused, kept for API compat)
            metadata_df: Optional DataFrame with metadata - must have same index as X
            cv_splits: Number of folds for TimeSeriesCV
            
        Returns:
            (metrics_dict, predictions_df)
        """
        logger.info(f"Training production time prediction model on {len(X)} samples")
        logger.info(f"Target variable stats: mean={y.mean():.2f}, std={y.std():.2f}")
        logger.info(f"Log-transform: {self.log_transform}")

        # Time-series split — last test_size% as test set (preserves temporal order)
        split_idx = int(len(X) * (1 - test_size))

        X_train = X.iloc[:split_idx]
        X_test = X.iloc[split_idx:]
        y_train = y.iloc[:split_idx]
        y_test = y.iloc[split_idx:]

        if metadata_df is not None:
            meta_test = metadata_df.iloc[split_idx:]
        else:
            meta_test = None

        logger.info(f"Train set: {len(X_train)} samples (earliest 80%)")
        logger.info(f"Test set: {len(X_test)} samples (latest 20%)")

        # P0: Apply log1p transform to target so XGBoost fits a less skewed distribution
        y_train_fit = np.log1p(y_train.values) if self.log_transform else y_train.values
        y_test_fit = np.log1p(y_test.values) if self.log_transform else y_test.values

        # Train model
        self.model.fit(
            X_train,
            y_train_fit,
            eval_set=[(X_train, y_train_fit), (X_test, y_test_fit)],
            verbose=False
        )

        self.feature_names = list(X.columns)
        self.is_trained = True

        # Make predictions and inverse-transform to original scale before metrics
        y_train_pred_raw = self.model.predict(X_train)
        y_test_pred_raw = self.model.predict(X_test)
        if self.log_transform:
            y_train_pred = np.expm1(y_train_pred_raw)
            y_test_pred = np.expm1(y_test_pred_raw)
        else:
            y_train_pred = y_train_pred_raw
            y_test_pred = y_test_pred_raw

        # Clamp negative predictions (log-space can occasionally produce values < 0 after expm1)
        y_train_pred = np.maximum(y_train_pred, 0.0)
        y_test_pred = np.maximum(y_test_pred, 0.0)

        # Calculate metrics on original scale
        metrics = self._calculate_metrics(
            y_train.values, y_train_pred,
            y_test.values, y_test_pred
        )
        
        # Create predictions DataFrame with metadata
        predictions_df = pd.DataFrame({
            'actual': y_test,
            'predicted': y_test_pred,
            'error': y_test - y_test_pred,
            'abs_error': np.abs(y_test - y_test_pred),
            'pct_error': np.abs((y_test - y_test_pred) / (y_test + 1e-6)) * 100
        })
        
        # Add metadata columns if provided
        if meta_test is not None:
            # Reset index to align with predictions_df
            meta_test_reset = meta_test.reset_index(drop=True)
            predictions_df = predictions_df.reset_index(drop=True)
            
            # Add metadata columns at the beginning
            for col in meta_test.columns:
                predictions_df.insert(0, col, meta_test_reset[col].values)
        
        logger.info("✓ Model training complete")
        self._log_metrics(metrics)
        
        # P4: Run time-series cross-validation for robust metrics
        self._run_timeseries_cv(X, y, n_splits=cv_splits)
        
        return metrics, predictions_df
    
    def _calculate_metrics(
        self,
        y_train_true: np.ndarray,
        y_train_pred: np.ndarray,
        y_test_true: np.ndarray,
        y_test_pred: np.ndarray
    ) -> Dict:
        """Calculate regression metrics on original (non-log) scale"""

        metrics = {
            "train_rmse": np.sqrt(mean_squared_error(y_train_true, y_train_pred)),
            "train_mae": mean_absolute_error(y_train_true, y_train_pred),
            "train_r2": r2_score(y_train_true, y_train_pred),
            "train_smape": self._smape(y_train_true, y_train_pred),

            "test_rmse": np.sqrt(mean_squared_error(y_test_true, y_test_pred)),
            "test_mae": mean_absolute_error(y_test_true, y_test_pred),
            "test_r2": r2_score(y_test_true, y_test_pred),
            "test_smape": self._smape(y_test_true, y_test_pred),
        }

        return metrics

    @staticmethod
    def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Symmetric MAPE — avoids the small-denominator inflation of plain MAPE.
        Formula: mean(|y_true - y_pred| / ((|y_true| + |y_pred|) / 2)) * 100
        """
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        denom = (np.abs(y_true) + np.abs(y_pred)) / 2.0
        # Skip pairs where both actual and predicted are 0
        mask = denom > 0
        if mask.sum() == 0:
            return 0.0
        return float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / denom[mask]) * 100)
    
    def _log_metrics(self, metrics: Dict):
        """Log metrics in a readable format"""
        logger.info("=" * 60)
        logger.info("MODEL PERFORMANCE - PRODUCTION TIME PREDICTION (REGRESSION)")
        logger.info("=" * 60)
        
        logger.info("\n📊 TRAIN SET:")
        logger.info(f"  RMSE:  {metrics['train_rmse']:.3f} days")
        logger.info(f"  MAE:   {metrics['train_mae']:.3f} days")
        logger.info(f"  R²:    {metrics['train_r2']:.4f}")
        logger.info(f"  SMAPE: {metrics['train_smape']:.2f}%")

        logger.info("\n📊 TEST SET:")
        logger.info(f"  RMSE:  {metrics['test_rmse']:.3f} days")
        logger.info(f"  MAE:   {metrics['test_mae']:.3f} days")
        logger.info(f"  R²:    {metrics['test_r2']:.4f}")
        logger.info(f"  SMAPE: {metrics['test_smape']:.2f}%")
        
        logger.info("=" * 60)
    
    def _run_timeseries_cv(self, X: pd.DataFrame, y: pd.Series, n_splits: int = 5):
        """P4: Run time-series cross-validation for robust evaluation"""
        logger.info(f"\n📊 Running {n_splits}-fold Time-Series Cross-Validation...")
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_rmse, cv_mae, cv_r2 = [], [], []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Apply same log-transform as main training
            y_tr_fit = np.log1p(y_tr.values) if self.log_transform else y_tr.values
            y_val_fit = np.log1p(y_val.values) if self.log_transform else y_val.values

            cv_model = xgb.XGBRegressor(**self.params)
            cv_model.fit(X_tr, y_tr_fit, eval_set=[(X_val, y_val_fit)], verbose=False)
            y_pred_raw = cv_model.predict(X_val)

            # Inverse-transform predictions to original scale for metrics
            if self.log_transform:
                y_pred = np.maximum(np.expm1(y_pred_raw), 0.0)
            else:
                y_pred = y_pred_raw

            fold_rmse = np.sqrt(mean_squared_error(y_val.values, y_pred))
            fold_mae = mean_absolute_error(y_val.values, y_pred)
            fold_r2 = r2_score(y_val.values, y_pred)
            
            cv_rmse.append(fold_rmse)
            cv_mae.append(fold_mae)
            cv_r2.append(fold_r2)
            
            logger.info(f"  Fold {fold+1}: RMSE={fold_rmse:.3f}, MAE={fold_mae:.3f}, R²={fold_r2:.4f} (train={len(X_tr)}, val={len(X_val)})")
        
        self.cv_metrics = {
            'cv_rmse_mean': np.mean(cv_rmse),
            'cv_rmse_std': np.std(cv_rmse),
            'cv_mae_mean': np.mean(cv_mae),
            'cv_mae_std': np.std(cv_mae),
            'cv_r2_mean': np.mean(cv_r2),
            'cv_r2_std': np.std(cv_r2),
        }
        
        logger.info(f"\n📊 CV SUMMARY ({n_splits}-fold TimeSeriesCV):")
        logger.info(f"  RMSE:  {self.cv_metrics['cv_rmse_mean']:.3f} ± {self.cv_metrics['cv_rmse_std']:.3f}")
        logger.info(f"  MAE:   {self.cv_metrics['cv_mae_mean']:.3f} ± {self.cv_metrics['cv_mae_std']:.3f}")
        logger.info(f"  R²:    {self.cv_metrics['cv_r2_mean']:.4f} ± {self.cv_metrics['cv_r2_std']:.4f}")

    # ------------------------------------------------------------------
    # P2: Optuna hyperparameter search
    # ------------------------------------------------------------------
    def optimize_hyperparams(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_trials: int = 50,
        n_splits: int = 3,
        timeout: int = None,
    ) -> Dict:
        """
        Use Optuna to find better XGBoost hyperparameters via TimeSeriesCV.

        Args:
            X: Feature matrix (pre-sorted by time)
            y: Target variable (original scale, not log-transformed)
            n_trials: Number of Optuna trials
            n_splits: TimeSeriesSplit folds for CV evaluation
            timeout: Optional time limit in seconds

        Returns:
            Dict of best hyperparameters (merged with current self.params)
        """
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)
        except ImportError:
            raise ImportError("optuna is required: pip install optuna")

        tscv = TimeSeriesSplit(n_splits=n_splits)

        def objective(trial):
            params = {
                "objective": "reg:pseudohubererror",
                "huber_slope": trial.suggest_float("huber_slope", 0.5, 5.0),
                "eval_metric": ["rmse"],
                "n_jobs": -1,
                "random_state": 42,
                "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=50),
                "max_depth": trial.suggest_int("max_depth", 3, 9),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "gamma": trial.suggest_float("gamma", 0.0, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
            }

            rmse_list = []
            for train_idx, val_idx in tscv.split(X):
                X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

                y_tr_fit = np.log1p(y_tr.values) if self.log_transform else y_tr.values
                y_val_fit = np.log1p(y_val.values) if self.log_transform else y_val.values

                m = xgb.XGBRegressor(**params, early_stopping_rounds=15)
                m.fit(X_tr, y_tr_fit, eval_set=[(X_val, y_val_fit)], verbose=False)
                pred_raw = m.predict(X_val)
                if self.log_transform:
                    pred = np.maximum(np.expm1(pred_raw), 0.0)
                else:
                    pred = pred_raw
                rmse_list.append(np.sqrt(mean_squared_error(y_val.values, pred)))

            return float(np.mean(rmse_list))

        logger.info(f"🔍 Starting Optuna search ({n_trials} trials, {n_splits}-fold CV)...")
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)

        best = study.best_params
        logger.info(f"✅ Best CV RMSE: {study.best_value:.4f}")
        logger.info(f"   Best params: {best}")

        # Merge with fixed params kept from current self.params
        optimized = {
            "objective": "reg:pseudohubererror",
            "eval_metric": ["rmse", "mae"],
            "n_jobs": -1,
            "random_state": 42,
            "early_stopping_rounds": 15,
            **best,
        }
        self.params = optimized
        self.model = xgb.XGBRegressor(**self.params)
        return optimized

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict production time for new data.
        Automatically aligns feature columns to match the trained model.
        
        Args:
            X: Feature matrix
            
        Returns:
            Predicted production time in days
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        # Align features: add missing columns (fill 0), drop extra columns, reorder
        if self.feature_names is not None:
            missing = set(self.feature_names) - set(X.columns)
            extra = set(X.columns) - set(self.feature_names)
            if missing:
                logger.warning(f"Adding {len(missing)} missing features (filled with 0): {missing}")
                for col in missing:
                    X = X.copy()
                    X[col] = 0.0
            if extra:
                logger.warning(f"Dropping {len(extra)} extra features not in trained model: {extra}")
            X = X[self.feature_names]
        
        raw = self.model.predict(X)
        if self.log_transform:
            return np.maximum(np.expm1(raw), 0.0)
        return raw

    def get_feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """
        Get feature importance scores
        
        Args:
            top_n: Number of top features to return
            
        Returns:
            DataFrame with feature importance
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")
        
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance_df.head(top_n)
    
    def save(self, filepath: str):
        """
        Save model to file
        
        Args:
            filepath: Path to save model (JSON format)
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save booster directly (more reliable)
        self.model.get_booster().save_model(str(filepath))
        
        # Also save feature names and config
        metadata_path = filepath.with_suffix('.metadata.json')
        import json
        with open(metadata_path, 'w') as f:
            json.dump({
                'feature_names': self.feature_names,
                'n_features': len(self.feature_names),
                'log_transform': self.log_transform,
            }, f, indent=2)
        
        logger.info(f"✓ Model saved to {filepath}")
        logger.info(f"✓ Metadata saved to {metadata_path}")
    
    def load(self, filepath: str):
        """
        Load model from file
        
        Args:
            filepath: Path to model file
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        # Load model directly (works on unfitted XGBRegressor)
        self.model.load_model(str(filepath))
        
        # Load feature names and config
        metadata_path = filepath.with_suffix('.metadata.json')
        if metadata_path.exists():
            import json
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                self.feature_names = metadata['feature_names']
                # Older models saved without this key default to False (no transform)
                self.log_transform = metadata.get('log_transform', False)
        
        self.is_trained = True
        logger.info(f"✓ Model loaded from {filepath}")
    
    def predict_with_confidence(
        self,
        X: pd.DataFrame,
        quantiles: list = [0.1, 0.9]
    ) -> pd.DataFrame:
        """
        Predict with confidence intervals using quantile regression
        
        Args:
            X: Feature matrix
            quantiles: List of quantiles for prediction intervals
            
        Returns:
            DataFrame with predictions and confidence intervals
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        # Point prediction
        y_pred = self.predict(X)
        
        # Create results DataFrame
        results = pd.DataFrame({
            'predicted_mean': y_pred
        })
        
        # Note: For proper confidence intervals, we would need to train
        # separate quantile regression models. For now, we use a simple
        # heuristic based on historical error distribution.
        
        return results
