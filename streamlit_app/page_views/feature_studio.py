"""
页面2: 特征工程工作室 (Feature Studio)
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys
sys.path.append('.')

from streamlit_app.ui import render_page_header, render_section_card


def show_feature_studio():
    render_page_header("Feature Studio", "配置、生成和分析预测特征", "Features")

    if st.session_state.get('merged_df') is None:
        st.warning("请先在“数据管理”页面加载数据。")
        return

    df = st.session_state['merged_df']

    tab_config, tab_result, tab_analysis = st.tabs(["特征配置", "特征结果", "特征分析"])

    # ── Tab 1: 特征配置 ──
    with tab_config:
        with render_section_card("Feature Configuration", "选择特征组并配置回溯参数"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**基础特征**")
                feat_basic = st.checkbox("基础特征 (13个)", value=True, key="feat_basic",
                                          help="计划工期、订单数量、产线产能等")
                feat_time = st.checkbox("高级时间特征 (6个)", value=True, key="feat_time",
                                         help="周末、月初月末、季度末等")
                feat_material = st.checkbox("物料特征 (4个)", value=True, key="feat_material",
                                             help="物料族编码、产品类型等")
                feat_line = st.checkbox("产线特征 (4个)", value=True, key="feat_line",
                                         help="产线编码、生产复杂度等")
                feat_history = st.checkbox("历史特征 (5个)", value=True, key="feat_history",
                                            help="历史延迟率、平均延迟天数等 (最重要!)")
                feat_interaction = st.checkbox("交互特征 (4个)", value=True, key="feat_interaction",
                                                help="特征间交叉组合")

            with col2:
                st.markdown("**MRP特征 (可选)**")
                has_mrp = st.session_state.get('mrp_dataframes') is not None
                if not has_mrp:
                    st.caption("未检测到MRP数据文件，以下选项不可用")

                feat_mrp_supply = st.checkbox("MRP供需特征 (6个)", value=False,
                                               disabled=not has_mrp, key="feat_mrp_supply",
                                               help="物料缺口、供需比等")
                feat_mrp_procurement = st.checkbox("采购交付特征 (3个)", value=False,
                                                    disabled=not has_mrp, key="feat_mrp_procurement",
                                                    help="供应商准时率、采购延迟等")
                feat_mrp_bom = st.checkbox("BOM/库存特征 (5个)", value=False,
                                            disabled=not has_mrp, key="feat_mrp_bom",
                                            help="BOM复杂度、库存覆盖等")

                st.markdown("---")
                st.markdown("**参数设置**")
                lookback_days = st.slider("历史回溯天数", 30, 180, 90, 10, key="lookback_days")

        # 保存配置
        st.session_state['feature_config'] = {
            'basic': feat_basic,
            'time_advanced': feat_time,
            'material': feat_material,
            'production_line': feat_line,
            'historical': feat_history,
            'interaction': feat_interaction,
            'mrp_supply': feat_mrp_supply,
            'mrp_procurement': feat_mrp_procurement,
            'mrp_bom': feat_mrp_bom,
            'lookback_days': lookback_days,
        }

        with render_section_card("Run Pipeline", "执行特征工程并刷新会话状态"):
            if st.button("执行特征工程", type="primary", key="run_features"):
                _run_feature_engineering(df)

    # ── Tab 2: 特征结果 ──
    with tab_result:
        if st.session_state.get('feature_df') is not None:
            feature_df = st.session_state['feature_df']
            feature_cols = st.session_state.get('feature_cols', [])

            with render_section_card("Feature Summary", "样本规模、特征数与缺失概览"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("总样本数", f"{len(feature_df):,}")
                with col2:
                    st.metric("特征数", f"{len(feature_cols)}")
                with col3:
                    if 'is_delayed' in feature_df.columns:
                        st.metric("延迟率", f"{feature_df['is_delayed'].mean():.1%}")
                with col4:
                    missing = feature_df[feature_cols].isnull().sum().sum()
                    st.metric("特征缺失值", f"{missing}")

            with render_section_card("Feature List", "每个特征的类型、缺失与分布统计"):
                feat_info = []
                for col in feature_cols:
                    if col in feature_df.columns:
                        feat_info.append({
                            '特征名': col,
                            '类型': str(feature_df[col].dtype),
                            '缺失': feature_df[col].isnull().sum(),
                            '均值': f"{feature_df[col].mean():.4f}" if feature_df[col].dtype in ['float64', 'int64'] else "N/A",
                            '标准差': f"{feature_df[col].std():.4f}" if feature_df[col].dtype in ['float64', 'int64'] else "N/A",
                        })
                st.dataframe(pd.DataFrame(feat_info), width='stretch', hide_index=True)

            with render_section_card("Feature Preview", "特征样本预览（前 50 行）"):
                st.dataframe(feature_df[feature_cols].head(50), width='stretch', height=400)
        else:
            st.info("请先在 '特征配置' 中执行特征工程")

    # ── Tab 3: 特征分析 ──
    with tab_analysis:
        if st.session_state.get('feature_df') is not None:
            _show_feature_analysis()
        else:
            st.info("请先执行特征工程")


def _run_feature_engineering(df):
    """执行特征工程"""
    from src.data_processing.aps_feature_engineer import APSFeatureEngineer
    from src.data_processing.mrp_feature_engineer import MRPFeatureEngineer

    config = st.session_state.get('feature_config', {})
    progress = st.progress(0)
    status = st.empty()

    try:
        # Step 1: 基础APS特征
        status.text("执行 APS 特征工程...")
        progress.progress(20)

        engineer = APSFeatureEngineer(lookback_days=config.get('lookback_days', 90))
        feature_df = engineer.transform(df)
        feature_cols = []

        # 根据配置选择特征
        all_features = engineer.get_feature_names()

        # 基础特征组映射
        group_map = {
            'basic': all_features[:13],
            'time_advanced': all_features[13:19],
            'material': all_features[19:23],
            'production_line': all_features[23:27],
            'historical': all_features[27:32],
            'interaction': all_features[32:36],
        }

        for group_name, group_features in group_map.items():
            if config.get(group_name, True):
                feature_cols.extend([f for f in group_features if f in feature_df.columns])

        progress.progress(50)

        # Step 2: MRP特征 (如果启用)
        mrp_dfs = st.session_state.get('mrp_dataframes', {})
        if any(config.get(k, False) for k in ['mrp_supply', 'mrp_procurement', 'mrp_bom']):
            status.text("生成 MRP 特征...")
            mrp_engineer = MRPFeatureEngineer()
            feature_df = mrp_engineer.transform(
                feature_df,
                mrp_df=mrp_dfs.get('mrp_results.csv'),
                po_df=mrp_dfs.get('purchase_orders.csv'),
                bom_df=mrp_dfs.get('bom_data.csv'),
                stock_df=mrp_dfs.get('stock_levels.csv'),
            )

            mrp_feature_names = mrp_engineer.get_mrp_feature_names()
            available_mrp = [f for f in mrp_feature_names if f in feature_df.columns]
            feature_cols.extend(available_mrp)

        progress.progress(80)

        # Step 3: 清理
        status.text("清理数据...")
        feature_cols = [f for f in feature_cols if f in feature_df.columns]

        # 填充NaN
        for col in feature_cols:
            if feature_df[col].isnull().any():
                if feature_df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                    feature_df[col] = feature_df[col].fillna(feature_df[col].median())
                else:
                    feature_df[col] = feature_df[col].fillna(0)

        progress.progress(100)

        st.session_state['feature_df'] = feature_df
        st.session_state['feature_cols'] = feature_cols
        st.session_state['features_ready'] = True

        status.empty()
        progress.empty()
        st.success(f"特征工程完成，生成 {len(feature_cols)} 个特征，{len(feature_df)} 个样本。")
        st.rerun()

    except Exception as e:
        progress.empty()
        status.empty()
        st.error(f"特征工程失败: {e}")
        import traceback
        st.code(traceback.format_exc())


def _show_feature_analysis():
    """特征分析视图"""
    feature_df = st.session_state['feature_df']
    feature_cols = st.session_state['feature_cols']

    with render_section_card("Correlation & Label Analysis", "相关性矩阵与标签差异对比"):
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("特征相关性矩阵")
            numeric_features = feature_df[feature_cols].select_dtypes(include=[np.number])
            if len(numeric_features.columns) > 0:
                corr = numeric_features.corr()
                if len(corr) > 15:
                    top_features = corr.abs().mean().sort_values(ascending=False).head(15).index
                    corr = corr.loc[top_features, top_features]

                fig = px.imshow(
                    corr,
                    color_continuous_scale='RdBu_r',
                    zmin=-1, zmax=1,
                    title="Top 特征相关性"
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, width='stretch')

        with col2:
            st.subheader("特征与标签关系")
            if 'is_delayed' in feature_df.columns:
                selected_feat = st.selectbox("选择特征", feature_cols, key="feat_analysis_select")
                if selected_feat and selected_feat in feature_df.columns:
                    fig = px.box(
                        feature_df,
                        x='is_delayed',
                        y=selected_feat,
                        labels={'is_delayed': '是否延迟', selected_feat: selected_feat},
                        title=f"{selected_feat} vs 延迟状态",
                        color='is_delayed',
                        color_discrete_map={0: '#4caf50', 1: '#f44336'}
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, width='stretch')

    with render_section_card("Feature Distribution", "特征分布形态与标签差异"):
        dist_feat = st.selectbox("选择特征查看分布", feature_cols, key="feat_dist_select")
        if dist_feat and dist_feat in feature_df.columns:
            fig = px.histogram(
                feature_df, x=dist_feat, nbins=50,
                color='is_delayed' if 'is_delayed' in feature_df.columns else None,
                barmode='overlay', opacity=0.7,
                color_discrete_map={0: '#4caf50', 1: '#f44336'},
                title=f"{dist_feat} 分布"
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, width='stretch')
