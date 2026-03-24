"""
模型评估引擎 — 支持多维度、多版本、时序追踪
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
    classification_report
)
from loguru import logger
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalResult:
    """评估结果"""
    model_version: str
    eval_type: str  # 'training' | 'validation' | 'test' | 'production'
    metrics: dict = field(default_factory=dict)
    sliced_metrics: list = field(default_factory=list)
    y_true: np.ndarray = None
    y_pred: np.ndarray = None
    y_proba: np.ndarray = None


class ModelEvaluator:
    """模型评估引擎"""

    def evaluate(self, model, X, y, model_version="unknown",
                 eval_type="validation") -> EvalResult:
        """
        执行全面评估

        Args:
            model: 训练好的模型 (需有predict/predict_proba方法)
            X: 特征矩阵
            y: 真实标签
            model_version: 模型版本
            eval_type: 评估类型

        Returns:
            EvalResult
        """
        y_pred = model.predict(X)
        y_proba = model.predict_proba(X)[:, 1]

        metrics = {
            'accuracy': float(accuracy_score(y, y_pred)),
            'precision': float(precision_score(y, y_pred, zero_division=0)),
            'recall': float(recall_score(y, y_pred, zero_division=0)),
            'f1_score': float(f1_score(y, y_pred, zero_division=0)),
            'roc_auc': float(roc_auc_score(y, y_proba)),
            'confusion_matrix': confusion_matrix(y, y_pred).tolist(),
            'total_samples': len(y),
            'positive_samples': int(y.sum()),
            'negative_samples': int(len(y) - y.sum()),
        }

        return EvalResult(
            model_version=model_version,
            eval_type=eval_type,
            metrics=metrics,
            y_true=y,
            y_pred=y_pred,
            y_proba=y_proba,
        )

    def sliced_evaluation(self, model, df: pd.DataFrame,
                           feature_names: list, slice_column: str,
                           target_col: str = 'is_delayed',
                           min_samples: int = 10) -> pd.DataFrame:
        """
        按维度分层评估

        Args:
            model: 训练好的模型
            df: 含特征和分组列的DataFrame
            feature_names: 特征列名
            slice_column: 分层列名 (如 'material', 'production_line')
            target_col: 目标列
            min_samples: 最少样本数

        Returns:
            分层指标DataFrame
        """
        results = []

        for slice_value, group in df.groupby(slice_column):
            if len(group) < min_samples:
                continue

            X = group[feature_names].values
            y = group[target_col].values

            if len(np.unique(y)) < 2:
                continue

            y_pred = model.predict(X)
            y_proba = model.predict_proba(X)[:, 1]

            results.append({
                'slice': str(slice_value),
                'samples': len(group),
                'delay_rate': float(y.mean()),
                'accuracy': float(accuracy_score(y, y_pred)),
                'precision': float(precision_score(y, y_pred, zero_division=0)),
                'recall': float(recall_score(y, y_pred, zero_division=0)),
                'f1_score': float(f1_score(y, y_pred, zero_division=0)),
                'roc_auc': float(roc_auc_score(y, y_proba)),
            })

        return pd.DataFrame(results).sort_values('f1_score', ascending=True)

    def temporal_evaluation(self, model, df: pd.DataFrame,
                             feature_names: list,
                             time_column: str = 'planned_start_date',
                             target_col: str = 'is_delayed',
                             freq: str = 'M') -> pd.DataFrame:
        """
        时间滑动窗口评估

        Args:
            model: 训练好的模型
            df: 含特征和时间列的DataFrame
            feature_names: 特征列名
            time_column: 时间列
            target_col: 目标列
            freq: 时间粒度 ('W', 'M', 'Q')

        Returns:
            各时间段指标DataFrame
        """
        df = df.copy()
        df['_eval_period'] = df[time_column].dt.to_period(freq).astype(str)

        results = []
        for period, group in df.groupby('_eval_period'):
            if len(group) < 10:
                continue

            X = group[feature_names].values
            y = group[target_col].values

            if len(np.unique(y)) < 2:
                continue

            y_pred = model.predict(X)
            y_proba = model.predict_proba(X)[:, 1]

            results.append({
                'period': period,
                'samples': len(group),
                'delay_rate': float(y.mean()),
                'accuracy': float(accuracy_score(y, y_pred)),
                'precision': float(precision_score(y, y_pred, zero_division=0)),
                'recall': float(recall_score(y, y_pred, zero_division=0)),
                'f1_score': float(f1_score(y, y_pred, zero_division=0)),
                'roc_auc': float(roc_auc_score(y, y_proba)),
            })

        return pd.DataFrame(results)

    def compare_models(self, result_a: EvalResult, result_b: EvalResult) -> dict:
        """
        A/B 模型对比

        Returns:
            各指标的差异字典
        """
        comparison = {}
        metric_keys = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']

        for key in metric_keys:
            val_a = result_a.metrics.get(key, 0)
            val_b = result_b.metrics.get(key, 0)
            comparison[key] = {
                'model_a': val_a,
                'model_b': val_b,
                'diff': val_a - val_b,
                'improved': val_a > val_b,
            }

        return comparison

    def get_error_analysis(self, df: pd.DataFrame, feature_names: list,
                            y_true: np.ndarray, y_pred: np.ndarray,
                            y_proba: np.ndarray) -> dict:
        """
        错误预测分析

        Returns:
            {'false_positives': DataFrame, 'false_negatives': DataFrame}
        """
        df_analysis = df.copy()
        df_analysis['predicted'] = y_pred
        df_analysis['probability'] = y_proba
        df_analysis['actual'] = y_true
        df_analysis['correct'] = (y_pred == y_true)
        df_analysis['error_magnitude'] = np.abs(y_proba - y_true)

        fp_mask = (y_pred == 1) & (y_true == 0)
        fn_mask = (y_pred == 0) & (y_true == 1)

        return {
            'false_positives': df_analysis[fp_mask].sort_values('probability', ascending=False),
            'false_negatives': df_analysis[fn_mask].sort_values('probability', ascending=True),
            'fp_count': int(fp_mask.sum()),
            'fn_count': int(fn_mask.sum()),
            'total_errors': int((~df_analysis['correct']).sum()),
            'error_rate': float((~df_analysis['correct']).mean()),
        }
