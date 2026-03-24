"""
指标卡片组件
"""
import streamlit as st


def render_metrics_row(metrics: dict, columns=5, delta_metrics: dict = None):
    """
    渲染一行指标卡片

    Args:
        metrics: {metric_name: value} 字典
        columns: 列数
        delta_metrics: {metric_name: delta_value} 可选的变化值
    """
    cols = st.columns(columns)
    for i, (name, value) in enumerate(metrics.items()):
        col = cols[i % columns]
        with col:
            delta = None
            delta_color = "normal"
            if delta_metrics and name in delta_metrics:
                delta_val = delta_metrics[name]
                delta = f"{delta_val:+.1%}" if isinstance(delta_val, float) else str(delta_val)
                delta_color = "normal" if delta_val >= 0 else "inverse"

            if isinstance(value, float):
                if value <= 1.0:
                    display_value = f"{value:.1%}"
                else:
                    display_value = f"{value:.3f}"
            else:
                display_value = str(value)

            st.metric(label=name, value=display_value, delta=delta, delta_color=delta_color)


def render_model_info_card(model_version: str, model_path: str, train_samples: int,
                            feature_count: int, train_date: str = ""):
    """渲染模型信息卡片"""
    st.markdown(f"""
    **模型版本**: `{model_version}`
    **模型路径**: `{model_path}`
    **训练样本**: {train_samples:,}
    **特征数量**: {feature_count}
    **训练时间**: {train_date}
    """)


def render_step_progress(steps: list, current_step: int):
    """
    渲染步骤进度条

    Args:
        steps: 步骤名称列表
        current_step: 当前步骤索引 (0-based), -1表示全部完成
    """
    total = len(steps)
    if current_step < 0:
        progress = 1.0
    else:
        progress = current_step / total

    st.progress(progress)

    for i, step_name in enumerate(steps):
        if current_step < 0 or i < current_step:
            st.markdown(f"&emsp; :white_check_mark: ~~{step_name}~~")
        elif i == current_step:
            st.markdown(f"&emsp; :hourglass_flowing_sand: **{step_name}**")
        else:
            st.markdown(f"&emsp; :white_circle: {step_name}")


def render_data_summary(df, title="数据概要"):
    """渲染数据摘要信息"""
    import pandas as pd

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总行数", f"{len(df):,}")
    with col2:
        st.metric("总列数", f"{len(df.columns)}")
    with col3:
        missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
        st.metric("缺失率", f"{missing_pct:.1f}%")
    with col4:
        dup = df.duplicated().sum()
        st.metric("重复行", f"{dup}")
