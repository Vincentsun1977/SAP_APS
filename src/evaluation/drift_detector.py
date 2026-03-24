"""
模型漂移检测器
"""
import numpy as np
import pandas as pd
from loguru import logger


class DriftDetector:
    """检测模型性能漂移和特征分布漂移"""

    def calculate_psi(self, expected: np.ndarray, actual: np.ndarray,
                       n_bins: int = 10) -> float:
        """
        计算 Population Stability Index (PSI)

        PSI < 0.10: 无显著漂移
        0.10 <= PSI < 0.25: 轻微漂移
        PSI >= 0.25: 显著漂移

        Args:
            expected: 参考分布 (训练集)
            actual: 当前分布 (生产数据)
            n_bins: 分箱数

        Returns:
            PSI值
        """
        expected = expected[~np.isnan(expected)]
        actual = actual[~np.isnan(actual)]

        if len(expected) == 0 or len(actual) == 0:
            return 0.0

        breakpoints = np.linspace(
            min(expected.min(), actual.min()),
            max(expected.max(), actual.max()),
            n_bins + 1
        )

        expected_counts = np.histogram(expected, bins=breakpoints)[0]
        actual_counts = np.histogram(actual, bins=breakpoints)[0]

        # 避免除零
        expected_pcts = (expected_counts + 1) / (len(expected) + n_bins)
        actual_pcts = (actual_counts + 1) / (len(actual) + n_bins)

        psi = np.sum((actual_pcts - expected_pcts) * np.log(actual_pcts / expected_pcts))

        return float(psi)

    def check_feature_drift(self, train_df: pd.DataFrame,
                             current_df: pd.DataFrame,
                             feature_names: list) -> pd.DataFrame:
        """
        检查所有特征的分布漂移

        Returns:
            DataFrame: feature, psi, status
        """
        results = []
        for feat in feature_names:
            if feat not in train_df.columns or feat not in current_df.columns:
                continue

            psi = self.calculate_psi(
                train_df[feat].values.astype(float),
                current_df[feat].values.astype(float)
            )

            if psi >= 0.25:
                status = "显著漂移"
            elif psi >= 0.10:
                status = "轻微漂移"
            else:
                status = "稳定"

            results.append({
                'feature': feat,
                'psi': round(psi, 4),
                'status': status,
            })

        df = pd.DataFrame(results).sort_values('psi', ascending=False)
        return df

    def check_performance_drift(self, metrics_over_time: pd.DataFrame,
                                 metric_col: str = 'accuracy',
                                 window: int = 3,
                                 threshold: float = 0.05) -> dict:
        """
        检查模型性能是否随时间退化

        Args:
            metrics_over_time: 包含 period 和 metric 列的DataFrame
            metric_col: 要检测的指标列
            window: 滑动窗口大小
            threshold: 退化阈值

        Returns:
            {'is_drifting': bool, 'trend': float, 'recent_mean': float, 'baseline_mean': float}
        """
        if len(metrics_over_time) < window * 2:
            return {
                'is_drifting': False,
                'trend': 0.0,
                'recent_mean': float(metrics_over_time[metric_col].mean()),
                'baseline_mean': float(metrics_over_time[metric_col].mean()),
                'message': '数据不足，无法判断趋势'
            }

        values = metrics_over_time[metric_col].values

        baseline_mean = float(np.mean(values[:window]))
        recent_mean = float(np.mean(values[-window:]))
        trend = recent_mean - baseline_mean

        is_drifting = trend < -threshold

        if is_drifting:
            message = f"{metric_col} 下降 {abs(trend):.3f}，可能需要重新训练模型"
        elif trend < 0:
            message = f"{metric_col} 轻微下降 {abs(trend):.3f}，建议持续监控"
        else:
            message = f"{metric_col} 稳定或上升，模型表现良好"

        return {
            'is_drifting': is_drifting,
            'trend': float(trend),
            'recent_mean': recent_mean,
            'baseline_mean': baseline_mean,
            'message': message,
        }
