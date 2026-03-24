"""
页面4: 模型测试实验室 (Testing Lab)
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys
sys.path.append('.')

from streamlit_app.ui import render_page_header, render_section_card


def show_testing_lab():
    render_page_header("Testing Lab", "单条预测、批量测试、误差分析", "Testing")

    if not st.session_state.get('model_trained', False):
        # 尝试加载已有模型
        _try_load_existing_model()
        if not st.session_state.get('model_trained', False):
            st.warning("请先在“模型训练”页面训练模型，或确认 `models/` 目录中已有模型文件。")
            return

    tab_single, tab_batch, tab_error = st.tabs(["单条预测", "批量测试", "误差分析"])

    with tab_single:
        _show_single_prediction()

    with tab_batch:
        _show_batch_test()

    with tab_error:
        _show_error_analysis()


def _try_load_existing_model():
    """尝试加载已有模型"""
    import glob
    from src.models.xgboost_model import ProductionDelayModel
    from src.data_processing.aps_feature_engineer import APSFeatureEngineer

    model_files = glob.glob("models/aps_xgb_model_*.json")
    if not model_files:
        return

    latest_model = max(model_files)
    model = ProductionDelayModel()
    model.load(latest_model)

    engineer = APSFeatureEngineer()
    model.feature_names = engineer.get_feature_names()

    st.session_state['trained_model'] = model.model
    st.session_state['model_trained'] = True
    st.session_state['model_path'] = latest_model
    st.session_state['feature_cols'] = engineer.get_feature_names()


def _show_single_prediction():
    """单条预测"""
    with render_section_card("Single Prediction", "手动输入订单并查看风险评估"):
        st.subheader("手动输入订单信息")

        model = st.session_state.get('trained_model')
        feature_cols = st.session_state.get('feature_cols', [])

        # 如果有已加载的特征数据，用它来获取范围参考
        feature_df = st.session_state.get('feature_df')

        col1, col2, col3 = st.columns(3)

        with col1:
            order_qty = st.number_input("订单数量", min_value=1, value=5, key="test_qty")
            production_time = st.number_input("单位生产时长 (小时)", min_value=0.1, value=2.5, step=0.1, key="test_time")
            line_capacity = st.number_input("产线日产能", min_value=1, value=10, key="test_cap")

        with col2:
            planned_duration = st.number_input("计划生产天数", min_value=1, value=14, key="test_dur")
            constraint = st.number_input("约束值", min_value=0.0, value=1.0, step=0.1, key="test_con")
            earliest_start = st.number_input("最早开工天数", min_value=0, value=3, key="test_early")

        with col3:
            start_month = st.selectbox("开始月份", range(1, 13), index=2, key="test_month")
            start_weekday = st.selectbox("开始星期", range(0, 7), format_func=lambda x: ['周一','周二','周三','周四','周五','周六','周日'][x], key="test_weekday")
            start_quarter = (start_month - 1) // 3 + 1

    if st.button("执行预测", type="primary", key="predict_single"):
        try:
            # 构建特征向量
            qty_cap_ratio = order_qty / max(line_capacity, 1)
            expected_days = order_qty * production_time / max(line_capacity, 1)

            feature_values = {
                'planned_duration_days': planned_duration,
                'order_quantity': order_qty,
                'total_production_time': production_time,
                'line_capacity': line_capacity,
                'constraint': constraint,
                'earliest_start_days': earliest_start,
                'qty_capacity_ratio': qty_cap_ratio,
                'expected_production_days': expected_days,
                'planned_start_month': start_month,
                'planned_start_weekday': start_weekday,
                'planned_start_quarter': start_quarter,
                'planned_start_year': 2026,
                'has_supervisor': 1,
                'is_weekend': 1 if start_weekday >= 5 else 0,
                'is_month_start': 0,
                'is_month_end': 0,
                'is_quarter_end': 0,
                'is_year_end': 1 if start_month == 12 else 0,
                'week_of_year': start_month * 4,
                'log_order_quantity': np.log1p(order_qty),
                'material_family_encoded': 0,
                'is_convac': 0,
                'is_vsc': 0,
                'production_line_encoded': 0,
                'production_complexity': production_time * constraint,
                'is_large_order': 1 if order_qty > 10 else 0,
                'production_time_category_encoded': 1,
                'material_delay_rate_90d': 0.3,
                'line_delay_rate_90d': 0.3,
                'material_family_delay_rate': 0.3,
                'material_avg_delay_days': 2.0,
                'material_production_count_30d': 5,
                'qty_time_interaction': order_qty * production_time,
                'capacity_holiday_interaction': qty_cap_ratio * (1 if start_month in [12,1,2] else 0),
                'large_order_history_interaction': (1 if order_qty > 10 else 0) * 0.3,
                'complexity_capacity_interaction': production_time * constraint * qty_cap_ratio,
            }

            X = np.array([[feature_values.get(f, 0) for f in feature_cols]])
            proba = model.predict_proba(X)[0, 1]

            with render_section_card("Prediction Result", "延迟概率与动作建议"):
                col_r1, col_r2 = st.columns([1, 1])

                with col_r1:
                    from streamlit_app.components.charts import render_gauge
                    fig = render_gauge(proba, "延迟概率", height=250)
                    st.plotly_chart(fig, width='stretch')

                with col_r2:
                    if proba >= 0.7:
                        st.error(f"高风险 — 延迟概率: {proba:.1%}")
                        st.error("**建议**: 立即介入，调整排程或增加资源")
                    elif proba >= 0.4:
                        st.warning(f"中风险 — 延迟概率: {proba:.1%}")
                        st.warning("**建议**: 加强监控，准备应急方案")
                    else:
                        st.success(f"低风险 — 延迟概率: {proba:.1%}")
                        st.success("**建议**: 按计划执行，正常跟踪")

        except Exception as e:
            st.error(f"预测失败: {e}")


def _show_batch_test():
    """批量测试"""
    with render_section_card("Batch Test", "验证集或全量样本上的批量评估"):
        st.subheader("批量测试")

        model = st.session_state.get('trained_model')
        feature_cols = st.session_state.get('feature_cols', [])
        feature_df = st.session_state.get('feature_df')
        result = st.session_state.get('training_result')

        # 使用验证集数据
        if result is not None and result.X_val is not None:
            st.info(f"使用验证集数据进行测试 ({len(result.X_val)} 个样本)")

            if st.button("运行批量测试", type="primary", key="run_batch"):
                X_val = result.X_val
                y_val = result.y_val
                y_pred = model.predict(X_val)
                y_proba = model.predict_proba(X_val)[:, 1]

                from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

                acc = accuracy_score(y_val, y_pred)
                prec = precision_score(y_val, y_pred, zero_division=0)
                rec = recall_score(y_val, y_pred, zero_division=0)
                f1 = f1_score(y_val, y_pred, zero_division=0)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("准确率", f"{acc:.1%}")
                with col2:
                    st.metric("精确率", f"{prec:.1%}")
                with col3:
                    st.metric("召回率", f"{rec:.1%}")
                with col4:
                    st.metric("F1", f"{f1:.3f}")

                from streamlit_app.components.charts import render_prediction_distribution
                fig = render_prediction_distribution(y_proba, y_val)
                st.plotly_chart(fig, width='stretch')

                st.session_state['test_y_true'] = y_val
                st.session_state['test_y_pred'] = y_pred
                st.session_state['test_y_proba'] = y_proba

        elif feature_df is not None and 'is_delayed' in feature_df.columns:
            st.info("使用全量特征数据进行测试")
            if st.button("运行批量测试", type="primary", key="run_batch_full"):
                X = feature_df[feature_cols].values
                y = feature_df['is_delayed'].values
                y_pred = model.predict(X)
                y_proba = model.predict_proba(X)[:, 1]

                from sklearn.metrics import accuracy_score
                st.metric("全量数据准确率", f"{accuracy_score(y, y_pred):.1%}")

                st.session_state['test_y_true'] = y
                st.session_state['test_y_pred'] = y_pred
                st.session_state['test_y_proba'] = y_proba
        else:
            st.info("需要先完成特征工程和模型训练才能进行批量测试")

    with render_section_card("Custom Test Dataset", "上传新测试集（结构需与训练特征一致）"):
        test_file = st.file_uploader("上传测试数据CSV", type=["csv"], key="upload_test")
        if test_file is not None:
            st.info("上传的测试数据需包含与训练数据相同的特征列")


def _show_error_analysis():
    """误差分析"""
    with render_section_card("Error Analysis", "误报/漏报与置信度结构分析"):
        st.subheader("误差分析")

        y_true = st.session_state.get('test_y_true')
        y_pred = st.session_state.get('test_y_pred')
        y_proba = st.session_state.get('test_y_proba')

        if y_true is None:
            st.info("请先在 '批量测试' 中运行测试")
            return

        correct = (y_true == y_pred).sum()
        total = len(y_true)
        fp = ((y_pred == 1) & (y_true == 0)).sum()
        fn = ((y_pred == 0) & (y_true == 1)).sum()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总样本", total)
        with col2:
            st.metric("正确预测", f"{correct} ({correct/total:.1%})")
        with col3:
            st.metric("误报 (FP)", f"{fp}", help="实际准时但预测为延迟")
        with col4:
            st.metric("漏报 (FN)", f"{fn}", help="实际延迟但预测为准时")

        st.subheader("按预测概率区间分析准确率")
        bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        bin_labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(len(bins)-1)]
        bin_indices = np.digitize(y_proba, bins) - 1

        bin_stats = []
        for i in range(len(bins)-1):
            mask = bin_indices == i
            if mask.sum() > 0:
                bin_acc = (y_true[mask] == y_pred[mask]).mean()
                bin_delay_rate = y_true[mask].mean()
                bin_stats.append({
                    '概率区间': bin_labels[i],
                    '样本数': int(mask.sum()),
                    '准确率': f"{bin_acc:.1%}",
                    '实际延迟率': f"{bin_delay_rate:.1%}",
                })

        if bin_stats:
            st.dataframe(pd.DataFrame(bin_stats), width='stretch', hide_index=True)

        st.subheader("预测置信度分析")
        confidence = np.abs(y_proba - 0.5) * 2  # 归一化到0-1
        fig = px.histogram(
            x=confidence,
            nbins=50,
            labels={'x': '预测置信度', 'y': '样本数'},
            title="预测置信度分布 (越高越确信)",
            color_discrete_sequence=['#3498db']
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, width='stretch')
