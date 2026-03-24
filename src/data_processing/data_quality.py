"""
数据质量检查模块
"""
import pandas as pd
import numpy as np
from loguru import logger
from typing import Tuple


class DataQualityChecker:
    """数据质量检查器"""

    def check_dataframe(self, df: pd.DataFrame, name: str = "dataset",
                         required_cols: list = None) -> dict:
        """
        全面检查DataFrame质量

        Returns:
            quality report dict
        """
        report = {
            'name': name,
            'rows': len(df),
            'columns': len(df.columns),
            'duplicates': int(df.duplicated().sum()),
            'total_missing': int(df.isnull().sum().sum()),
            'total_cells': len(df) * len(df.columns),
            'missing_pct': 0.0,
            'column_stats': {},
            'issues': [],
            'warnings': [],
            'score': 100,  # 满分100
        }

        if report['total_cells'] > 0:
            report['missing_pct'] = round(report['total_missing'] / report['total_cells'] * 100, 2)

        # 逐列统计
        for col in df.columns:
            col_stat = {
                'dtype': str(df[col].dtype),
                'missing': int(df[col].isnull().sum()),
                'missing_pct': round(df[col].isnull().sum() / len(df) * 100, 1),
                'unique': int(df[col].nunique()),
            }
            if df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                col_stat['min'] = float(df[col].min()) if not df[col].isnull().all() else None
                col_stat['max'] = float(df[col].max()) if not df[col].isnull().all() else None
                col_stat['mean'] = float(df[col].mean()) if not df[col].isnull().all() else None
            report['column_stats'][col] = col_stat

        # 必需列检查
        if required_cols:
            missing_required = [c for c in required_cols if c not in df.columns]
            if missing_required:
                report['issues'].append(f"缺少必需列: {missing_required}")
                report['score'] -= 20 * len(missing_required)

        # 空列检查
        empty_cols = [c for c in df.columns if df[c].isnull().all()]
        if empty_cols:
            report['issues'].append(f"完全为空的列: {empty_cols}")
            report['score'] -= 10

        # 高缺失率检查
        high_missing = {c: s['missing_pct'] for c, s in report['column_stats'].items() if s['missing_pct'] > 50}
        if high_missing:
            report['warnings'].append(f"缺失率>50%的列: {list(high_missing.keys())}")
            report['score'] -= 5

        # 重复行检查
        if report['duplicates'] > 0:
            dup_pct = report['duplicates'] / report['rows'] * 100
            report['warnings'].append(f"发现 {report['duplicates']} 行重复数据 ({dup_pct:.1f}%)")
            if dup_pct > 10:
                report['score'] -= 10

        report['score'] = max(0, report['score'])

        return report

    def validate_production_data(self, df: pd.DataFrame) -> Tuple[bool, list]:
        """
        验证生产订单数据完整性

        Returns:
            (is_valid, issues)
        """
        issues = []

        # 日期逻辑检查
        if 'planned_start_date' in df.columns and 'planned_finish_date' in df.columns:
            invalid = df[df['planned_finish_date'] < df['planned_start_date']]
            if len(invalid) > 0:
                issues.append(f"{len(invalid)} 条记录计划完成日期早于开始日期")

        if 'actual_finish_date' in df.columns and 'planned_start_date' in df.columns:
            invalid = df[
                df['actual_finish_date'].notna() &
                (df['actual_finish_date'] < df['planned_start_date'])
            ]
            if len(invalid) > 0:
                issues.append(f"{len(invalid)} 条记录实际完成日期早于计划开始日期")

        # 数值范围检查
        if 'order_quantity' in df.columns:
            neg = (df['order_quantity'] < 0).sum()
            if neg > 0:
                issues.append(f"{neg} 条记录订单数量为负数")

        return len(issues) == 0, issues
