"""
页面5: 模型评估中心 (Evaluation Center)
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys
sys.path.append('.')

from src.config.paths import get_aps_model_paths_str, get_latest_aps_model_path
from streamlit_app.ui import render_page_header, render_section_card


def show_evaluation_center():
    render_page_header("Evaluation Center", "综合评估、版本对比、分层分析、漂移监控", "Evaluation")

    tab_overview, tab_roc, tab_sliced, tab_drift, tab_compare = st.tabs([
        "综合指标", "ROC/PR 曲线", "分层评估", "漂移监控", "模型对比"
    ])

    with tab_overview:
        _show_overview()
    with tab_roc:
        _show_roc_pr()
    with tab_sliced:
        _show_sliced_evaluation()
    with tab_drift:
        _show_drift_monitoring()
    with tab_compare:
        _show_model_comparison()


def _show_overview():
    """综合指标视图"""
    result = st.session_state.get('training_result')

    if result is None:
        _try_evaluate_from_data()
        result = st.session_state.get('training_result')

    if result is None:
        st.warning("请先完成模型训练，或确认已有可用模型与数据。")
        return

    metrics = result.metrics

    from streamlit_app.components.charts import render_confusion_matrix, render_feature_importance

    with render_section_card("Core Metrics", "模型整体性能指标"):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("准确率", f"{metrics['accuracy']:.1%}")
        with col2:
            st.metric("精确率", f"{metrics['precision']:.1%}")
        with col3:
            st.metric("召回率", f"{metrics['recall']:.1%}")
        with col4:
            st.metric("F1 Score", f"{metrics['f1_score']:.3f}")
        with col5:
            st.metric("ROC AUC", f"{metrics['roc_auc']:.3f}")

    with render_section_card("Model Diagnostics", "混淆矩阵、特征重要性与概率分布"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("混淆矩阵")
            fig = render_confusion_matrix(metrics['confusion_matrix'])
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("特征重要性 Top 15")
            fig = render_feature_importance(result.feature_importance)
            st.plotly_chart(fig, use_container_width=True)

        if result.y_val is not None:
            st.subheader("预测概率分布")
            y_proba = result.model.predict_proba(result.X_val)[:, 1]
            from streamlit_app.components.charts import render_prediction_distribution
            fig = render_prediction_distribution(y_proba, result.y_val)
            st.plotly_chart(fig, use_container_width=True)


def _show_roc_pr():
    """ROC和PR曲线"""
    result = st.session_state.get('training_result')

    if result is None or result.X_val is None:
        st.info("需要训练结果中包含验证集数据")
        return

    from streamlit_app.components.charts import render_roc_curve, render_pr_curve

    y_proba = result.model.predict_proba(result.X_val)[:, 1]

    with render_section_card("ROC / PR Curves", "分类阈值变化下的性能表现"):
        col1, col2 = st.columns(2)

        with col1:
            fig = render_roc_curve(result.y_val, y_proba)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = render_pr_curve(result.y_val, y_proba)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("阈值分析")
        st.caption("调整分类阈值观察指标变化")
        threshold = st.slider("分类阈值", 0.1, 0.9, 0.5, 0.05, key="eval_threshold")

        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        y_pred_custom = (y_proba >= threshold).astype(int)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("准确率", f"{accuracy_score(result.y_val, y_pred_custom):.1%}")
        with col2:
            st.metric("精确率", f"{precision_score(result.y_val, y_pred_custom, zero_division=0):.1%}")
        with col3:
            st.metric("召回率", f"{recall_score(result.y_val, y_pred_custom, zero_division=0):.1%}")
        with col4:
            st.metric("F1", f"{f1_score(result.y_val, y_pred_custom, zero_division=0):.3f}")


def _show_sliced_evaluation():
    """分层评估"""
    feature_df = st.session_state.get('feature_df')
    model = st.session_state.get('trained_model')
    feature_cols = st.session_state.get('feature_cols', [])

    if feature_df is None or model is None:
        st.info("需要特征数据和已训练模型")
        return

    from src.evaluation.model_evaluator import ModelEvaluator
    evaluator = ModelEvaluator()

    # 维度选择
    available_slices = []
    for col in ['material', 'production_line', 'planned_start_quarter',
                 'planned_start_month', 'material_family']:
        if col in feature_df.columns:
            available_slices.append(col)

    if not available_slices:
        st.warning("未找到可用的分层维度")
        return

    slice_col = st.selectbox("选择分层维度", available_slices, key="slice_dim")
    min_samples = st.slider("最少样本数", 5, 50, 10, key="slice_min")

    if st.button("执行分层评估", type="primary", key="run_sliced"):
        with st.spinner("分层评估中..."):
            sliced_df = evaluator.sliced_evaluation(
                model, feature_df, feature_cols, slice_col,
                min_samples=min_samples
            )

            if len(sliced_df) == 0:
                st.warning("没有满足最少样本数的分层")
                return

            st.session_state['sliced_eval_result'] = sliced_df

    # 显示结果
    sliced_df = st.session_state.get('sliced_eval_result')
    if sliced_df is not None and len(sliced_df) > 0:
        with render_section_card("Sliced Evaluation Result", f"按 {slice_col} 维度查看表现差异"):
            st.subheader(f"按 {slice_col} 分层评估结果")

            fig = go.Figure(data=go.Bar(
                x=sliced_df['slice'],
                y=sliced_df['f1_score'],
                marker_color=[
                    '#f44336' if v < 0.6 else '#ff9800' if v < 0.8 else '#4caf50'
                    for v in sliced_df['f1_score']
                ],
                text=[f"{v:.3f}" for v in sliced_df['f1_score']],
                textposition='outside'
            ))
            fig.update_layout(
                title=f"各 {slice_col} 的 F1 Score",
                xaxis_title=slice_col,
                yaxis_title="F1 Score",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                sliced_df.style.format({
                    'delay_rate': '{:.1%}',
                    'accuracy': '{:.1%}',
                    'precision': '{:.1%}',
                    'recall': '{:.1%}',
                    'f1_score': '{:.3f}',
                    'roc_auc': '{:.3f}',
                }),
                width='stretch',
                hide_index=True
            )

            weak = sliced_df[sliced_df['f1_score'] < 0.7]
            if len(weak) > 0:
                st.warning(f"发现 {len(weak)} 个薄弱区域 (F1 < 0.7): {', '.join(weak['slice'].tolist())}")


def _show_drift_monitoring():
    """漂移监控"""
    feature_df = st.session_state.get('feature_df')
    model = st.session_state.get('trained_model')
    feature_cols = st.session_state.get('feature_cols', [])

    if feature_df is None or model is None:
        st.info("需要特征数据和已训练模型")
        return

    from src.evaluation.model_evaluator import ModelEvaluator
    from src.evaluation.drift_detector import DriftDetector

    evaluator = ModelEvaluator()
    detector = DriftDetector()

    st.subheader("性能时间趋势")
    time_col = 'planned_start_date'
    if time_col not in feature_df.columns:
        st.warning(f"未找到时间列 '{time_col}'")
        return

    freq = st.selectbox("时间粒度", ['M', 'Q', 'W'], format_func=lambda x: {'M':'月', 'Q':'季度', 'W':'周'}[x], key="drift_freq")

    if st.button("执行漂移检测", type="primary", key="run_drift"):
        with st.spinner("计算中..."):
            temporal_df = evaluator.temporal_evaluation(
                model, feature_df, feature_cols, time_col, freq=freq
            )

            if len(temporal_df) == 0:
                st.warning("时间段过少，无法分析")
                return

            st.session_state['temporal_eval'] = temporal_df

    temporal_df = st.session_state.get('temporal_eval')
    if temporal_df is not None and len(temporal_df) > 0:
        with render_section_card("Temporal Drift Result", "模型性能与特征分布的时间漂移监控"):
            fig = go.Figure()
            for metric in ['accuracy', 'f1_score', 'roc_auc']:
                fig.add_trace(go.Scatter(
                    x=temporal_df['period'], y=temporal_df[metric],
                    mode='lines+markers', name=metric
                ))
            fig.update_layout(
                title="模型性能时间趋势",
                xaxis_title="时间段", yaxis_title="指标值",
                height=400, hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

            drift_result = detector.check_performance_drift(temporal_df, 'f1_score')
            if drift_result['is_drifting']:
                st.error(f"检测到性能漂移: {drift_result['message']}")
            else:
                st.success(drift_result['message'])

            st.subheader("特征分布漂移检测 (PSI)")
            st.caption("比较前半段数据(基线)与后半段数据(当前)的特征分布差异")

            mid = len(feature_df) // 2
            train_half = feature_df.iloc[:mid]
            current_half = feature_df.iloc[mid:]

            drift_df = detector.check_feature_drift(train_half, current_half, feature_cols)

            if len(drift_df) > 0:
                fig = go.Figure(go.Bar(
                    x=drift_df['feature'],
                    y=drift_df['psi'],
                    marker_color=[
                        '#f44336' if s == '显著漂移' else '#ff9800' if s == '轻微漂移' else '#4caf50'
                        for s in drift_df['status']
                    ],
                    text=drift_df['status'],
                    textposition='outside'
                ))
                fig.add_hline(y=0.25, line_dash="dash", line_color="red", annotation_text="显著漂移阈值")
                fig.add_hline(y=0.10, line_dash="dash", line_color="orange", annotation_text="轻微漂移阈值")
                fig.update_layout(title="特征PSI分布", height=400, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

                significant = drift_df[drift_df['status'] == '显著漂移']
                if len(significant) > 0:
                    st.warning(f"{len(significant)} 个特征存在显著分布漂移: {', '.join(significant['feature'].tolist())}")


def _show_model_comparison():
    """模型对比"""
    st.subheader("模型版本对比")

    model_files = get_aps_model_paths_str()

    if len(model_files) < 2:
        st.info("需要至少2个模型版本才能进行对比。请多次训练后再使用此功能。")

        # 显示已有模型
        if model_files:
            st.markdown("**已有模型:**")
            for f in model_files:
                st.markdown(f"- `{f}`")
        return

    col1, col2 = st.columns(2)
    with col1:
        model_a_path = st.selectbox("模型 A", model_files, index=len(model_files)-1, key="cmp_a")
    with col2:
        model_b_path = st.selectbox("模型 B", model_files, index=max(0, len(model_files)-2), key="cmp_b")

    if model_a_path == model_b_path:
        st.warning("请选择不同的模型版本进行对比")
        return

    feature_df = st.session_state.get('feature_df')
    feature_cols = st.session_state.get('feature_cols', [])

    if feature_df is None:
        st.warning("需要先加载特征数据")
        return

    if st.button("开始对比", type="primary", key="run_compare"):
        from src.models.xgboost_model import ProductionDelayModel
        from src.evaluation.model_evaluator import ModelEvaluator

        evaluator = ModelEvaluator()

        with st.spinner("加载模型并评估..."):
            # 加载两个模型
            model_a = ProductionDelayModel()
            model_a.load(model_a_path)
            model_b = ProductionDelayModel()
            model_b.load(model_b_path)

            X = feature_df[feature_cols].values
            y = feature_df['is_delayed'].values

            result_a = evaluator.evaluate(model_a.model, X, y, model_version=model_a_path)
            result_b = evaluator.evaluate(model_b.model, X, y, model_version=model_b_path)

            comparison = evaluator.compare_models(result_a, result_b)

        with render_section_card("Comparison Result", "模型版本指标与 ROC 表现对比"):
            st.subheader("指标对比")

            metrics_display = []
            for key, vals in comparison.items():
                metrics_display.append({
                    '指标': key,
                    '模型A': f"{vals['model_a']:.4f}",
                    '模型B': f"{vals['model_b']:.4f}",
                    '差异': f"{vals['diff']:+.4f}",
                    '更优': '模型A' if vals['improved'] else '模型B',
                })

            st.dataframe(pd.DataFrame(metrics_display), width='stretch', hide_index=True)

            from streamlit_app.components.charts import render_roc_comparison
            fig = render_roc_comparison({
                'Model A': (result_a.y_true, result_a.y_proba),
                'Model B': (result_b.y_true, result_b.y_proba),
            })
            st.plotly_chart(fig, use_container_width=True)


def _try_evaluate_from_data():
    """尝试从已有数据评估"""
    feature_df = st.session_state.get('feature_df')
    feature_cols = st.session_state.get('feature_cols', [])

    if feature_df is None or not feature_cols:
        return

    from src.models.xgboost_model import ProductionDelayModel
    from src.training.training_pipeline import TrainingResult

    latest = get_latest_aps_model_path()
    if latest is None:
        return

    model = ProductionDelayModel()
    model.load(str(latest))

    X = feature_df[feature_cols].values
    y = feature_df['is_delayed'].values

    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    y_pred = model.model.predict(X_val)
    y_proba = model.model.predict_proba(X_val)[:, 1]

    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

    metrics = {
        'accuracy': float(accuracy_score(y_val, y_pred)),
        'precision': float(precision_score(y_val, y_pred, zero_division=0)),
        'recall': float(recall_score(y_val, y_pred, zero_division=0)),
        'f1_score': float(f1_score(y_val, y_pred, zero_division=0)),
        'roc_auc': float(roc_auc_score(y_val, y_proba)),
        'confusion_matrix': confusion_matrix(y_val, y_pred).tolist(),
    }

    importance = model.model.feature_importances_
    importance_dict = dict(zip(feature_cols, importance))

    from src.data_processing.aps_feature_engineer import APSFeatureEngineer
    eng = APSFeatureEngineer()

    result = TrainingResult(
        model=model.model,
        metrics=metrics,
        model_path=str(latest),
        feature_names=feature_cols,
        feature_importance=importance_dict,
        train_samples=len(X_train),
        val_samples=len(X_val),
        X_train=X_train,
        X_val=X_val,
        y_train=y_train,
        y_val=y_val,
    )

    st.session_state['training_result'] = result
    st.session_state['trained_model'] = model.model
    st.session_state['model_trained'] = True
    st.session_state['model_path'] = str(latest)
