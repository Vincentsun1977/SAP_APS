"""
页面6: 生产Dashboard + 实时预测 + 风险物料 + 趋势分析
(从原 aps_dashboard.py 迁移并整合)
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import glob
import sys
sys.path.append('.')

from streamlit_app.ui import render_page_header, render_section_card


def _ensure_data_and_model():
    """确保数据和模型可用"""
    df = st.session_state.get('feature_df')
    model = st.session_state.get('trained_model')

    if df is None:
        # 尝试加载processed数据
        try:
            df = pd.read_csv("data/processed/aps_training_data_full.csv")
            df['planned_start_date'] = pd.to_datetime(df['planned_start_date'])
            st.session_state['feature_df'] = df
            st.session_state['merged_df'] = df
            st.session_state['data_loaded'] = True
        except Exception:
            return None, None

    if model is None:
        try:
            from src.models.xgboost_model import ProductionDelayModel
            from src.data_processing.aps_feature_engineer import APSFeatureEngineer

            model_files = glob.glob("models/aps_xgb_model_*.json")
            if model_files:
                latest = max(model_files)
                m = ProductionDelayModel()
                m.load(latest)
                engineer = APSFeatureEngineer()
                m.feature_names = engineer.get_feature_names()
                st.session_state['trained_model'] = m.model
                st.session_state['model_trained'] = True
                st.session_state['feature_cols'] = engineer.get_feature_names()
                model = m.model
        except Exception:
            pass

    return df, model


def show_production_dashboard():
    render_page_header("Apps Dashboard", "生产概览、延迟分布与核心趋势", "Overview")

    df, model = _ensure_data_and_model()
    if df is None:
        st.error("未找到数据，请先在“数据管理”页面加载数据。")
        return

    # KPI
    total_orders = len(df)
    delayed_orders = int(df['is_delayed'].sum()) if 'is_delayed' in df.columns else 0
    ontime_orders = total_orders - delayed_orders
    delay_rate = delayed_orders / max(total_orders, 1)
    avg_delay = df['delay_days'].mean() if 'delay_days' in df.columns else 0

    with render_section_card("Core Metrics", "全局生产状态与延迟核心指标"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总订单数", f"{total_orders:,}")
        with col2:
            st.metric("延迟率", f"{delay_rate:.1%}", delta=f"{delayed_orders} 延迟", delta_color="inverse")
        with col3:
            st.metric("准时订单", f"{ontime_orders:,}")
        with col4:
            st.metric("平均延迟", f"{avg_delay:.1f} 天")

    with render_section_card("Delay Distribution", "延迟比例与延迟天数分布"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("订单延迟分布")
            if 'is_delayed' in df.columns:
                delay_counts = df['is_delayed'].value_counts()
                fig = px.pie(
                    values=delay_counts.values,
                    names=['准时', '延迟'],
                    color_discrete_map={'准时': '#4caf50', '延迟': '#f44336'},
                    hole=0.4
                )
                fig.update_traces(textposition='inside', textinfo='percent+label+value')
                fig.update_layout(height=350)
                st.plotly_chart(fig, width='stretch')

        with col2:
            st.subheader("延迟天数分布")
            if 'delay_days' in df.columns:
                fig = px.histogram(df, x='delay_days', nbins=40,
                                  labels={'delay_days': '延迟天数', 'count': '订单数'},
                                  color_discrete_sequence=['#3498db'])
                fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="准时基准")
                fig.update_layout(height=350)
                st.plotly_chart(fig, width='stretch')

    # 月度趋势
    if 'planned_start_date' in df.columns:
        with render_section_card("Monthly Delay Trend", "订单总量与延迟率的联动趋势"):
            st.subheader("月度延迟趋势")
            df_temp = df.copy()
            df_temp['month'] = df_temp['planned_start_date'].dt.to_period('M').astype(str)
            monthly = df_temp.groupby('month').agg({'is_delayed': ['count', 'sum', 'mean']}).reset_index()
            monthly.columns = ['月份', '总订单', '延迟订单', '延迟率']
            monthly['延迟率'] = monthly['延迟率'] * 100

            fig = go.Figure()
            fig.add_trace(go.Bar(x=monthly['月份'], y=monthly['总订单'], name='总订单', marker_color='lightblue'))
            fig.add_trace(go.Scatter(x=monthly['月份'], y=monthly['延迟率'], name='延迟率(%)',
                                      yaxis='y2', marker_color='red', line=dict(width=3)))
            fig.update_layout(
                yaxis=dict(title='订单数'),
                yaxis2=dict(title='延迟率(%)', overlaying='y', side='right'),
                hovermode='x unified', height=400
            )
            st.plotly_chart(fig, width='stretch')

    # Top物料
    if 'material' in df.columns and 'order_quantity' in df.columns:
        with render_section_card("Top Materials", "生产量最高的关键物料分布"):
            st.subheader("生产量 Top 10 物料")
            top = df.groupby('material')['order_quantity'].sum().sort_values(ascending=False).head(10)
            fig = px.bar(x=top.index, y=top.values,
                         labels={'x': '物料', 'y': '总生产量'},
                         color=top.values, color_continuous_scale='Blues')
            fig.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig, width='stretch')


def show_realtime_prediction():
    render_page_header("Realtime Prediction", "查看订单延迟风险与建议动作", "Prediction")

    df, model = _ensure_data_and_model()
    if df is None or model is None:
        st.error("需要数据和已训练模型。")
        return

    feature_cols = st.session_state.get('feature_cols', [])
    if not feature_cols:
        from src.data_processing.aps_feature_engineer import APSFeatureEngineer
        feature_cols = APSFeatureEngineer().get_feature_names()

    available_features = [c for c in feature_cols if c in df.columns]
    if not available_features:
        st.error("特征列不匹配")
        return

    X = df[available_features].fillna(0).values
    y_true = df['is_delayed'].values if 'is_delayed' in df.columns else None

    st.info("将从历史数据中随机选择订单进行预测演示。")

    np.random.seed(42)
    sample_indices = np.random.choice(len(df), min(10, len(df)), replace=False)

    for idx in sample_indices:
        row = df.iloc[idx]
        X_sample = X[idx:idx+1]

        prob = model.predict_proba(X_sample)[0, 1]
        pred = "延迟" if prob > 0.5 else "准时"
        actual = "延迟" if (y_true is not None and y_true[idx] == 1) else "准时"

        if prob >= 0.7:
            risk_label = "高风险"
        elif prob >= 0.4:
            risk_label = "中风险"
        else:
            risk_label = "低风险"

        order_id = row.get('production_number', f'Order-{idx}')
        with st.expander(f"订单 {order_id} - {risk_label} ({prob:.1%})"):
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.markdown(f"""
                **物料**: {row.get('material', 'N/A')}
                **数量**: {row.get('order_quantity', 'N/A')}
                **产线**: {row.get('production_line', 'N/A')}
                """)

            with col2:
                from streamlit_app.components.charts import render_gauge
                fig = render_gauge(prob, height=200)
                st.plotly_chart(fig, width='stretch')

            with col3:
                st.markdown(f"""
                **预测**: {pred}
                **实际**: {actual}
                **结果**: {'匹配' if pred == actual else '不匹配'}
                """)

            if prob >= 0.7:
                st.error("**建议**: 立即介入，调整排程或增加资源")
            elif prob >= 0.4:
                st.warning("**建议**: 加强监控，准备应急方案")
            else:
                st.success("**建议**: 按计划执行，正常跟踪")


def show_risk_materials():
    render_page_header("Risk Materials", "筛选高延迟率物料并识别重点对象", "Risk")

    df, _ = _ensure_data_and_model()
    if df is None:
        st.error("未找到数据。")
        return

    if 'material' not in df.columns or 'is_delayed' not in df.columns:
        st.warning("数据缺少必要列")
        return

    material_stats = df.groupby('material').agg({
        'is_delayed': ['count', 'sum', 'mean'],
        'order_quantity': 'sum',
        'delay_days': 'mean'
    }).reset_index()
    material_stats.columns = ['物料', '总订单数', '延迟订单数', '延迟率', '总生产量', '平均延迟天数']

    # 筛选
    with render_section_card("Risk Filter", "筛选高风险物料范围"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            min_orders = st.slider("最少订单数", 1, 50, 10, key="risk_min_orders")
        with col_f2:
            min_delay_rate = st.slider("最低延迟率", 0.0, 1.0, 0.2, 0.05, key="risk_min_rate")

    high_risk = material_stats[
        (material_stats['总订单数'] >= min_orders) &
        (material_stats['延迟率'] >= min_delay_rate)
    ].sort_values('延迟率', ascending=False)

    with render_section_card("Risk Results", f"发现 {len(high_risk)} 个高风险物料"):
        if len(high_risk) > 0:
            display = high_risk.copy()
            display['延迟率'] = display['延迟率'].apply(lambda x: f"{x:.1%}")
            display['平均延迟天数'] = display['平均延迟天数'].apply(lambda x: f"{x:.1f}")
            st.dataframe(display, width='stretch', height=400, hide_index=True)

            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(high_risk.head(10), x='延迟率', y='物料', orientation='h',
                             color='延迟率', color_continuous_scale='Reds')
                fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'}, title="延迟率排名")
                st.plotly_chart(fig, width='stretch')

            with col2:
                fig = px.scatter(high_risk, x='总订单数', y='延迟率', size='总生产量',
                                 color='平均延迟天数', hover_data=['物料'],
                                 color_continuous_scale='RdYlGn_r', title="订单量 vs 延迟率")
                fig.update_layout(height=400)
                st.plotly_chart(fig, width='stretch')
        else:
            st.success("未发现符合条件的高风险物料。")


def show_trends():
    render_page_header("Production Dashboard", "分析订单量、延迟率与生产负载趋势", "Trends")

    df, _ = _ensure_data_and_model()
    if df is None:
        st.error("未找到数据。")
        return

    if 'planned_start_date' not in df.columns:
        st.warning("数据缺少 planned_start_date 列")
        return

    with render_section_card("Trend Granularity", "选择趋势聚合粒度"):
        time_grain = st.selectbox("选择时间粒度", ["周", "月", "季度"], key="trend_grain")

    df_temp = df.copy()
    if time_grain == "周":
        df_temp['period'] = df_temp['planned_start_date'].dt.to_period('W').astype(str)
    elif time_grain == "月":
        df_temp['period'] = df_temp['planned_start_date'].dt.to_period('M').astype(str)
    else:
        df_temp['period'] = df_temp['planned_start_date'].dt.to_period('Q').astype(str)

    period_stats = df_temp.groupby('period').agg({
        'is_delayed': ['count', 'sum', 'mean'],
        'delay_days': 'mean',
        'order_quantity': 'sum'
    }).reset_index()
    period_stats.columns = ['时间段', '总订单', '延迟订单', '延迟率', '平均延迟天数', '总生产量']
    period_stats['延迟率'] = period_stats['延迟率'] * 100

    with render_section_card("Trend Charts", "订单、延迟率和负载关系"):
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("订单量趋势")
            fig = px.line(period_stats, x='时间段', y=['总订单', '延迟订单'], markers=True)
            fig.update_layout(height=350)
            st.plotly_chart(fig, width='stretch')

        with col2:
            st.subheader("延迟率趋势")
            fig = px.line(period_stats, x='时间段', y='延迟率', markers=True)
            fig.add_hline(y=period_stats['延迟率'].mean(), line_dash="dash",
                         annotation_text=f"平均: {period_stats['延迟率'].mean():.1f}%")
            fig.update_layout(height=350)
            st.plotly_chart(fig, width='stretch')

        st.subheader("生产负载 vs 延迟率")
        fig = px.scatter(period_stats, x='总生产量', y='延迟率', size='总订单',
                         color='平均延迟天数', hover_data=['时间段'],
                         color_continuous_scale='RdYlGn_r')
        fig.update_layout(height=400)
        st.plotly_chart(fig, width='stretch')

    with render_section_card("Trend Data", "趋势明细统计表"):
        st.dataframe(period_stats, width='stretch', height=300, hide_index=True)
