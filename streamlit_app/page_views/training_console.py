"""
页面3: 模型训练控制台 (Training Console)
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
sys.path.append('.')

from streamlit_app.ui import render_page_header, render_section_card


def show_training_console():
    render_page_header("Training Console", "配置超参数、训练模型、实时监控训练过程", "Training")

    if not st.session_state.get('features_ready', False):
        st.warning("请先在“特征工程”页面生成特征。")
        return

    tab_config, tab_monitor, tab_result = st.tabs(["训练配置", "训练监控", "训练结果"])

    # ── Tab 1: 训练配置 ──
    with tab_config:
        with render_section_card("Training Setup", "配置超参数与训练策略"):
            col1, col2 = st.columns([1, 1])

            with col1:
                st.subheader("超参数设置")
                max_depth = st.slider("max_depth (树深度)", 3, 12, 6, key="hp_depth")
                learning_rate = st.select_slider(
                    "learning_rate (学习率)",
                    options=[0.01, 0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3],
                    value=0.1, key="hp_lr"
                )
                n_estimators = st.slider("n_estimators (树数量)", 50, 500, 100, 10, key="hp_trees")
                min_child_weight = st.slider("min_child_weight", 1, 10, 1, key="hp_mcw")
                subsample = st.slider("subsample (行采样)", 0.5, 1.0, 0.8, 0.05, key="hp_sub")
                colsample = st.slider("colsample_bytree (列采样)", 0.5, 1.0, 0.8, 0.05, key="hp_col")

            with col2:
                st.subheader("训练设置")
                test_size = st.slider("验证集比例", 0.1, 0.4, 0.2, 0.05, key="hp_test_size")
                early_stopping = st.slider("早停轮数", 5, 50, 10, key="hp_early")
                random_seed = st.number_input("随机种子", value=42, key="hp_seed")

                st.markdown("---")
                st.subheader("自动调参")
                use_optuna = st.checkbox("启用Optuna自动调参", value=False, key="hp_optuna")
                if use_optuna:
                    n_trials = st.slider("调参试验次数", 10, 200, 50, 10, key="hp_trials")
                    st.caption("自动调参会覆盖上方手动设置的超参数。")

                st.markdown("---")
                st.subheader("数据概况")
                feature_df = st.session_state.get('feature_df')
                feature_cols = st.session_state.get('feature_cols', [])
                if feature_df is not None:
                    st.markdown(f"- 样本数: **{len(feature_df):,}**")
                    st.markdown(f"- 特征数: **{len(feature_cols)}**")
                    if 'is_delayed' in feature_df.columns:
                        delay_rate = feature_df['is_delayed'].mean()
                        st.markdown(f"- 延迟率: **{delay_rate:.1%}**")
                        st.markdown(f"- 延迟样本: **{int(feature_df['is_delayed'].sum()):,}**")

        with render_section_card("Actions", "启动训练或重置参数"):
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                start_training = st.button("开始训练", type="primary", key="start_train")
            with col_btn2:
                if st.button("重置默认值", key="reset_params"):
                    st.rerun()

        if start_training:
            params = {
                'max_depth': max_depth,
                'learning_rate': learning_rate,
                'n_estimators': n_estimators,
                'min_child_weight': min_child_weight,
                'subsample': subsample,
                'colsample_bytree': colsample,
            }

            if use_optuna:
                _run_optuna_training(feature_df, feature_cols, test_size, n_trials, early_stopping, random_seed)
            else:
                _run_training(feature_df, feature_cols, params, test_size, early_stopping, random_seed)

    # ── Tab 2: 训练监控 ──
    with tab_monitor:
        _show_training_monitor()

    # ── Tab 3: 训练结果 ──
    with tab_result:
        _show_training_result()


def _run_training(feature_df, feature_cols, params, test_size, early_stopping, random_seed):
    """执行模型训练"""
    from src.training.training_pipeline import TrainingPipeline

    pipeline = TrainingPipeline()
    progress = st.progress(0)
    status = st.empty()

    def on_progress(step, total, message):
        progress.progress(step / total)
        status.text(f"[{step}/{total}] {message}")

    try:
        # 准备数据
        on_progress(1, 5, "准备训练数据...")
        X_train, X_val, y_train, y_val, dropped = pipeline.prepare_data(
            feature_df, feature_cols, test_size=test_size, random_state=random_seed
        )

        if dropped > 0:
            st.info(f"清理了 {dropped} 行含缺失值的数据")

        # 训练
        result = pipeline.train(
            X_train, y_train, X_val, y_val,
            feature_names=feature_cols,
            params=params,
            early_stopping_rounds=early_stopping,
            progress_callback=on_progress
        )

        progress.progress(1.0)
        status.empty()

        st.session_state['training_result'] = result
        st.session_state['trained_model'] = result.model
        st.session_state['model_trained'] = True
        st.session_state['training_params'] = params
        st.session_state['model_path'] = result.model_path

        st.success(f"训练完成，模型已保存至 `{result.model_path}`。")
        st.rerun()

    except Exception as e:
        progress.empty()
        status.empty()
        st.error(f"训练失败: {e}")
        import traceback
        st.code(traceback.format_exc())


def _run_optuna_training(feature_df, feature_cols, test_size, n_trials, early_stopping, random_seed):
    """使用Optuna自动调参训练"""
    from src.training.training_pipeline import TrainingPipeline

    pipeline = TrainingPipeline()
    progress = st.progress(0)
    status = st.empty()
    trial_log = st.empty()

    try:
        # 准备数据
        status.text("准备训练数据...")
        X_train, X_val, y_train, y_val, dropped = pipeline.prepare_data(
            feature_df, feature_cols, test_size=test_size, random_state=random_seed
        )

        # Optuna调参
        status.text("Optuna 自动调参中...")

        def on_trial_progress(step, total, message):
            progress.progress(step / total * 0.7)  # 70% for tuning
            trial_log.text(message)

        best_params, trial_results, best_auc = pipeline.run_optuna_tuning(
            X_train, y_train, X_val, y_val,
            n_trials=n_trials,
            progress_callback=on_trial_progress
        )

        st.info(f"最佳AUC: {best_auc:.4f}")
        with st.expander("最佳超参数"):
            st.json({k: v for k, v in best_params.items()
                     if k not in ['objective', 'eval_metric', 'random_state', 'n_jobs']})

        # 使用最佳参数重新训练
        status.text("使用最佳参数训练最终模型...")

        def on_final_progress(step, total, message):
            progress.progress(0.7 + step / total * 0.3)
            status.text(message)

        result = pipeline.train(
            X_train, y_train, X_val, y_val,
            feature_names=feature_cols,
            params=best_params,
            early_stopping_rounds=early_stopping,
            progress_callback=on_final_progress
        )

        progress.progress(1.0)
        status.empty()
        trial_log.empty()

        st.session_state['training_result'] = result
        st.session_state['trained_model'] = result.model
        st.session_state['model_trained'] = True
        st.session_state['training_params'] = best_params
        st.session_state['model_path'] = result.model_path
        st.session_state['optuna_trials'] = trial_results

        st.success(f"调参与训练完成，模型已保存至 `{result.model_path}`。")
        st.rerun()

    except Exception as e:
        progress.empty()
        status.empty()
        st.error(f"训练失败: {e}")
        import traceback
        st.code(traceback.format_exc())


def _show_training_monitor():
    """训练监控视图"""
    result = st.session_state.get('training_result')

    if result is None:
        st.info("训练完成后此处将显示训练过程曲线")
        return

    from streamlit_app.components.charts import render_training_curves

    with render_section_card("Training Curves", f"训练耗时: {result.training_time:.1f}s | 最佳轮次: {result.best_iteration}"):
        col1, col2 = st.columns(2)

        with col1:
            if result.train_loss and result.val_loss:
                fig = render_training_curves(result.train_loss, result.val_loss, "LogLoss")
                st.plotly_chart(fig, width='stretch')

        with col2:
            if result.train_auc and result.val_auc:
                fig = render_training_curves(result.train_auc, result.val_auc, "AUC")
                st.plotly_chart(fig, width='stretch')

        if result.train_error and result.val_error:
            fig = render_training_curves(result.train_error, result.val_error, "Error Rate")
            st.plotly_chart(fig, width='stretch')

    # Optuna trial可视化
    if st.session_state.get('optuna_trials'):
        with render_section_card("Optuna History", "自动调参试验过程"):
            trials = st.session_state['optuna_trials']
            trials_df = pd.DataFrame(trials)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trials_df['trial'], y=trials_df['auc'],
                mode='markers+lines',
                marker=dict(size=6),
                name='Trial AUC'
            ))
            fig.add_hline(y=trials_df['auc'].max(), line_dash="dash",
                          annotation_text=f"Best: {trials_df['auc'].max():.4f}")
            fig.update_layout(title="调参试验AUC变化", xaxis_title="Trial", yaxis_title="AUC", height=350)
            st.plotly_chart(fig, width='stretch')


def _show_training_result():
    """训练结果视图"""
    result = st.session_state.get('training_result')

    if result is None:
        st.info("训练完成后此处将显示模型性能指标")
        return

    from streamlit_app.components.charts import render_confusion_matrix, render_feature_importance

    metrics = result.metrics
    with render_section_card("Result Metrics", "训练后验证集核心指标"):
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

    with render_section_card("Diagnostics", "混淆矩阵与特征重要性"):
        col1, col2 = st.columns(2)

        with col1:
            cm = metrics['confusion_matrix']
            fig = render_confusion_matrix(cm)
            st.plotly_chart(fig, width='stretch')

            tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
            st.info(f"""
            **TN** (正确准时): {tn} | **FP** (误判延迟): {fp}
            **FN** (漏判延迟): {fn} | **TP** (正确延迟): {tp}
            """)

        with col2:
            fig = render_feature_importance(result.feature_importance)
            st.plotly_chart(fig, width='stretch')

    with render_section_card("Model Info", "模型文件与样本规模"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**模型路径**: `{result.model_path}`")
        with col2:
            st.markdown(f"**训练样本**: {result.train_samples:,}")
        with col3:
            st.markdown(f"**验证样本**: {result.val_samples:,}")
        with col4:
            st.markdown(f"**特征数**: {len(result.feature_names)}")
