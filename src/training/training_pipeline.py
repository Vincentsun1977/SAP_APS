"""
可视化训练流水线引擎 — 与Streamlit集成
"""
import xgboost as xgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)
from loguru import logger
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class TrainingResult:
    """训练结果"""
    model: object
    metrics: dict
    train_loss: list = field(default_factory=list)
    val_loss: list = field(default_factory=list)
    train_auc: list = field(default_factory=list)
    val_auc: list = field(default_factory=list)
    train_error: list = field(default_factory=list)
    val_error: list = field(default_factory=list)
    model_path: str = ""
    feature_names: list = field(default_factory=list)
    feature_importance: dict = field(default_factory=dict)
    train_samples: int = 0
    val_samples: int = 0
    best_iteration: int = 0
    training_time: float = 0.0
    X_train: np.ndarray = None
    X_val: np.ndarray = None
    y_train: np.ndarray = None
    y_val: np.ndarray = None


class EvalLogCallback(xgb.callback.TrainingCallback):
    """XGBoost训练回调 — 捕获每轮指标"""

    def __init__(self):
        self.train_loss = []
        self.val_loss = []
        self.train_auc = []
        self.val_auc = []
        self.train_error = []
        self.val_error = []

    def after_iteration(self, model, epoch, evals_log):
        if 'validation_0' in evals_log:
            log = evals_log['validation_0']
            if 'logloss' in log:
                self.train_loss.append(log['logloss'][-1])
            if 'auc' in log:
                self.train_auc.append(log['auc'][-1])
            if 'error' in log:
                self.train_error.append(log['error'][-1])

        if 'validation_1' in evals_log:
            log = evals_log['validation_1']
            if 'logloss' in log:
                self.val_loss.append(log['logloss'][-1])
            if 'auc' in log:
                self.val_auc.append(log['auc'][-1])
            if 'error' in log:
                self.val_error.append(log['error'][-1])

        return False


class TrainingPipeline:
    """可视化训练流水线"""

    def __init__(self):
        self.result = None

    def prepare_data(self, df: pd.DataFrame, feature_cols: list,
                     target_col: str = 'is_delayed',
                     test_size: float = 0.2, random_state: int = 42):
        """
        准备训练数据

        Returns:
            X_train, X_val, y_train, y_val, cleaned_count
        """
        df_clean = df[feature_cols + [target_col]].copy()
        initial_count = len(df_clean)
        df_clean = df_clean.dropna()
        dropped = initial_count - len(df_clean)

        X = df_clean[feature_cols].values
        y = df_clean[target_col].values

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        return X_train, X_val, y_train, y_val, dropped

    def train(self, X_train, y_train, X_val, y_val,
              feature_names: list,
              params: dict = None,
              early_stopping_rounds: int = 10,
              progress_callback: Optional[Callable] = None) -> TrainingResult:
        """
        执行模型训练

        Args:
            X_train, y_train: 训练数据
            X_val, y_val: 验证数据
            feature_names: 特征名列表
            params: XGBoost超参数
            early_stopping_rounds: 早停轮数
            progress_callback: 进度回调 fn(step, total, message)
        """
        import time
        start_time = time.time()

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
        }

        if params:
            default_params.update(params)

        # 自动设置class weight
        scale_pos_weight = (len(y_train) - y_train.sum()) / max(y_train.sum(), 1)
        default_params['scale_pos_weight'] = scale_pos_weight

        if progress_callback:
            progress_callback(1, 5, "初始化模型...")

        # 创建回调
        eval_callback = EvalLogCallback()

        model = xgb.XGBClassifier(**default_params, callbacks=[eval_callback])

        if progress_callback:
            progress_callback(2, 5, "训练模型中...")

        model.fit(
            X_train, y_train,
            eval_set=[(X_train, y_train), (X_val, y_val)],
            verbose=False
        )

        if progress_callback:
            progress_callback(3, 5, "评估模型...")

        # 评估
        y_pred = model.predict(X_val)
        y_proba = model.predict_proba(X_val)[:, 1]

        metrics = {
            'accuracy': float(accuracy_score(y_val, y_pred)),
            'precision': float(precision_score(y_val, y_pred, zero_division=0)),
            'recall': float(recall_score(y_val, y_pred, zero_division=0)),
            'f1_score': float(f1_score(y_val, y_pred, zero_division=0)),
            'roc_auc': float(roc_auc_score(y_val, y_proba)),
            'confusion_matrix': confusion_matrix(y_val, y_pred).tolist(),
        }

        # 特征重要性
        importance = model.feature_importances_
        importance_dict = dict(zip(feature_names, importance))

        if progress_callback:
            progress_callback(4, 5, "保存模型...")

        # 保存模型
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = f"models/aps_xgb_model_{timestamp}.json"
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        model.save_model(model_path)

        training_time = time.time() - start_time

        if progress_callback:
            progress_callback(5, 5, "训练完成!")

        best_iter = getattr(model, 'best_iteration', len(eval_callback.train_loss))

        self.result = TrainingResult(
            model=model,
            metrics=metrics,
            train_loss=eval_callback.train_loss,
            val_loss=eval_callback.val_loss,
            train_auc=eval_callback.train_auc,
            val_auc=eval_callback.val_auc,
            train_error=eval_callback.train_error,
            val_error=eval_callback.val_error,
            model_path=model_path,
            feature_names=feature_names,
            feature_importance=importance_dict,
            train_samples=len(X_train),
            val_samples=len(X_val),
            best_iteration=best_iter,
            training_time=training_time,
            X_train=X_train,
            X_val=X_val,
            y_train=y_train,
            y_val=y_val,
        )

        return self.result

    def run_optuna_tuning(self, X_train, y_train, X_val, y_val,
                          n_trials: int = 50,
                          progress_callback: Optional[Callable] = None) -> dict:
        """使用Optuna进行超参数调优"""
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        best_params = {}
        trial_results = []

        def objective(trial):
            params = {
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'gamma': trial.suggest_float('gamma', 0, 5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 5),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 5),
            }

            model = xgb.XGBClassifier(
                **params,
                objective='binary:logistic',
                eval_metric='logloss',
                random_state=42,
                n_jobs=-1,
            )
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            y_proba = model.predict_proba(X_val)[:, 1]
            score = roc_auc_score(y_val, y_proba)

            trial_results.append({
                'trial': trial.number,
                'auc': score,
                'params': params
            })

            if progress_callback:
                progress_callback(
                    trial.number + 1, n_trials,
                    f"Trial {trial.number + 1}/{n_trials} - AUC: {score:.4f}"
                )

            return score

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)

        best_params = study.best_params
        best_params['objective'] = 'binary:logistic'
        best_params['eval_metric'] = ['logloss', 'auc', 'error']
        best_params['random_state'] = 42
        best_params['n_jobs'] = -1

        return best_params, trial_results, study.best_value
