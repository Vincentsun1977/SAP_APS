"""
数据质量报告组件
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def run_quality_check(df: pd.DataFrame, name: str = "dataset") -> dict:
    """
    执行数据质量检查

    Args:
        df: 待检查的DataFrame
        name: 数据集名称

    Returns:
        质量报告字典
    """
    report = {
        'name': name,
        'rows': len(df),
        'columns': len(df.columns),
        'duplicates': int(df.duplicated().sum()),
        'total_missing': int(df.isnull().sum().sum()),
        'missing_pct': float(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100),
        'column_types': df.dtypes.value_counts().to_dict(),
        'column_missing': df.isnull().sum().to_dict(),
        'column_missing_pct': (df.isnull().sum() / len(df) * 100).to_dict(),
        'issues': [],
        'warnings': [],
    }

    # 检查完全为空的列
    empty_cols = [col for col in df.columns if df[col].isnull().all()]
    if empty_cols:
        report['issues'].append(f"完全为空的列: {empty_cols}")

    # 检查高缺失率列 (>50%)
    high_missing = {col: pct for col, pct in report['column_missing_pct'].items() if pct > 50}
    if high_missing:
        report['warnings'].append(f"缺失率>50%的列: {list(high_missing.keys())}")

    # 检查重复行
    if report['duplicates'] > 0:
        report['warnings'].append(f"发现 {report['duplicates']} 行重复数据")

    # 检查日期列有效性
    date_cols = df.select_dtypes(include=['datetime64']).columns
    for col in date_cols:
        nat_count = df[col].isna().sum()
        if nat_count > 0:
            report['warnings'].append(f"日期列 '{col}' 有 {nat_count} 个无效值")

    return report


def render_quality_report(report: dict):
    """渲染数据质量报告"""
    st.subheader(f"数据质量报告: {report['name']}")

    # KPI行
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总行数", f"{report['rows']:,}")
    with col2:
        st.metric("总列数", f"{report['columns']}")
    with col3:
        st.metric("缺失率", f"{report['missing_pct']:.1f}%")
    with col4:
        st.metric("重复行", f"{report['duplicates']}")

    # 问题和警告
    if report['issues']:
        for issue in report['issues']:
            st.error(f"**问题**: {issue}")
    if report['warnings']:
        for warning in report['warnings']:
            st.warning(f"**警告**: {warning}")
    if not report['issues'] and not report['warnings']:
        st.success("数据质量检查通过，未发现问题")


def render_missing_heatmap(df: pd.DataFrame, height=300):
    """渲染列级缺失值热力图"""
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(1)

    # 只展示有缺失值的列
    has_missing = missing_pct[missing_pct > 0].sort_values(ascending=False)

    if len(has_missing) == 0:
        st.info("所有列均无缺失值")
        return

    fig = go.Figure(go.Bar(
        x=has_missing.index.tolist(),
        y=has_missing.values,
        marker_color=[
            '#f44336' if v > 50 else '#ff9800' if v > 20 else '#4caf50'
            for v in has_missing.values
        ],
        text=[f"{v:.1f}%" for v in has_missing.values],
        textposition='outside'
    ))
    fig.update_layout(
        title="列缺失率分布",
        xaxis_title="列名",
        yaxis_title="缺失率 (%)",
        height=height
    )
    st.plotly_chart(fig, use_container_width=True)


def render_column_distribution(df: pd.DataFrame, column: str, height=300):
    """渲染单列数据分布"""
    if df[column].dtype in ['float64', 'int64', 'float32', 'int32']:
        fig = px.histogram(
            df, x=column, nbins=40,
            title=f"{column} 分布",
            color_discrete_sequence=['#3498db']
        )
    else:
        value_counts = df[column].value_counts().head(20)
        fig = px.bar(
            x=value_counts.index.astype(str),
            y=value_counts.values,
            title=f"{column} 分布 (Top 20)",
            labels={'x': column, 'y': '数量'},
            color_discrete_sequence=['#3498db']
        )
    fig.update_layout(height=height)
    st.plotly_chart(fig, use_container_width=True)
