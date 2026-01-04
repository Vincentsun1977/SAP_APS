"""
XGBoost model for production order delay prediction
"""
import xgboost as xgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)
from loguru import logger
import joblib
from pathlib import Path
from typing import Tuple, Dict


class ProductionDelayModel:
    """XGBoost binary classifier for delay prediction"""
    
    def __init__(self, model_params: Dict = None):
        """
        Initialize model with hyperparameters
        
        Args:
            model_params: XGBoost parameters dict
        """
        default_params = {
            "objective": "binary:logistic",
            "eval_metric": ["logloss", "auc", "error"],
            "max_depth": 6,
            "min_child_weight": 1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "gamma": 0,
            "reg_alpha": 0,
            "reg_lambda": 1,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "random_state": 42,
            "n_jobs": -1,
            "scale_pos_weight": 1,
            "early_stopping_rounds": 10,
        }
        
        self.params = model_params or default_params
        self.model = xgb.XGBClassifier(**self.params)
        self.feature_names = None
        self.is_trained = False
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray = None,
        y_val: np.ndarray = None,
        early_stopping_rounds: int = 10
    ) -> Dict:
        """
        Train the XGBoost model
        
        Args:
            X_train: Training features
            y_train: Training labels (0=on-time, 1=delayed)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            early_stopping_rounds: Stop if no improvement
            
        Returns:
            Training metrics dictionary
        """
        logger.info("Starting model training")
        logger.info(f"Training samples: {len(X_train)}, Features: {X_train.shape[1]}")
        
        # Prepare eval set
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))
            logger.info(f"Validation samples: {len(X_val)}")
        
        # Train (XGBoost 3.0+ handles early stopping automatically if set in params)
        self.model.fit(
            X_train,
            y_train,
            eval_set=eval_set,
            verbose=True
        )
        
        self.is_trained = True
        
        # Evaluate on validation set
        if X_val is not None:
            metrics = self.evaluate(X_val, y_val)
            logger.info(f"Validation metrics: {metrics}")
            return metrics
        
        return {}
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class labels (0 or 1)
        
        Args:
            X: Features
            
        Returns:
            Predicted labels
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet. Call train() first.")
        
        return self.model.predict(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict delay probability
        
        Args:
            X: Features
            
        Returns:
            Probabilities array (shape: [n_samples, 2])
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet. Call train() first.")
        
        return self.model.predict_proba(X)
    
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """
        Evaluate model performance
        
        Args:
            X: Features
            y: True labels
            
        Returns:
            Dictionary of metrics
        """
        y_pred = self.predict(X)
        y_proba = self.predict_proba(X)[:, 1]
        
        metrics = {
            "accuracy": float(accuracy_score(y, y_pred)),
            "precision": float(precision_score(y, y_pred, zero_division=0)),
            "recall": float(recall_score(y, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, y_proba)),
        }
        
        # Confusion matrix
        cm = confusion_matrix(y, y_pred)
        metrics["confusion_matrix"] = cm.tolist()
        
        return metrics
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores
        
        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet.")
        
        importance = self.model.feature_importances_
        
        if self.feature_names:
            return dict(zip(self.feature_names, importance))
        else:
            return {f"feature_{i}": imp for i, imp in enumerate(importance)}
    
    def save(self, filepath: str):
        """Save model to file"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use joblib to save the entire model object
        joblib.dump(self.model, str(path))
        logger.info(f"Model saved to {filepath}")
    
    def load(self, filepath: str):
        """Load model from file"""
        self.model = joblib.load(filepath)
        self.is_trained = True
        logger.info(f"Model loaded from {filepath}")
    
    @staticmethod
    def split_data(
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Split data into train and validation sets
        
        Args:
            X: Features
            y: Labels
            test_size: Proportion for validation
            random_state: Random seed
            
        Returns:
            X_train, X_val, y_train, y_val
        """
        return train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y  # Maintain class distribution
        )
