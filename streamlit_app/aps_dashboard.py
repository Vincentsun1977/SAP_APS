"""
SAP Production Delay Prediction Dashboard
基于APS数据的生产延迟预测仪表板
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import numpy as np
sys.path.append('.')

from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer
from src.models.xgboost_model import ProductionDelayModel

# Page config
st.set_page_config(
    page_title="SAP生产延迟预测Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .risk-high {
        background-color: #ffebee;
        border-left: 4px solid #d32f2f;
        padding: 10px;
    }
    .risk-medium {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        padding: 10px;
    }
    .risk-low {
        background-color: #e8f5e9;
        border-left: 4px solid #4caf50;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_training_data():
    """加载训练数据"""
    try:
        df = pd.read_csv("data/processed/aps_training_data_full.csv")
        df['planned_start_date'] = pd.to_datetime(df['planned_start_date'])
        return df
    except:
        return None


@st.cache_resource
def load_aps_model():
    """加载APS模型"""
    import glob
    # 查找.pkl文件（新格式）或.json文件（旧格式）
    model_files = glob.glob("models/aps_xgb_model_*.pkl") + glob.glob("models/aps_xgb_model_*.json")
    if not model_files:
        return None
    
    latest_model = max(model_files)
    model = ProductionDelayModel()
    model.load(latest_model)
    
    # 设置特征名称
    engineer = APSFeatureEngineer()
    model.feature_names = engineer.get_feature_names()
    
    return model, latest_model


def main():
    # 标题
    st.markdown('<h1 class="main-header">📊 SAP生产延迟预测Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    # 侧边栏
    st.sidebar.title("🎛️ 控制面板")
    st.sidebar.markdown("###  导航菜单")
    
    page = st.sidebar.radio(
        "",
        ["🏠 总览Dashboard", "📊 模型性能", "🔮 实时预测", "⚠️ 风险物料", "📈 趋势分析"],
        label_visibility="collapsed"
    )
    
    # 加载数据和模型
    df = load_training_data()
    model_info = load_aps_model()
    
    if df is None:
        st.error("❌ 未找到训练数据，请先运行: `python scripts/train_aps_model.py`")
        return
    
    if model_info is None:
        st.error("❌ 未找到训练好的模型")
        return
    
    model, model_path = model_info
    
    # 侧边栏信息
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📌 系统信息")
    st.sidebar.info(f"""
    **数据量**: {len(df):,} 条订单  
    **时间范围**: {df['planned_start_date'].min().date()} 至 {df['planned_start_date'].max().date()}  
    **模型**: APS XGBoost  
    **特征数**: 36
    """)
    
    # 页面路由
    if page == "🏠 总览Dashboard":
        show_dashboard(df, model)
    elif page == "📊 模型性能":
        show_model_performance(df, model)
    elif page == "🔮 实时预测":
        show_prediction(df, model)
    elif page == "⚠️ 风险物料":
        show_risk_materials(df)
    else:
        show_trends(df)


def show_dashboard(df, model):
    """总览Dashboard"""
    st.header("🏠 总览Dashboard")
    
    # 核心KPI
    col1, col2, col3, col4 = st.columns(4)
    
    total_orders = len(df)
    delayed_orders = df['is_delayed'].sum()
    ontime_orders = total_orders - delayed_orders
    delay_rate = delayed_orders / total_orders
    avg_delay = df['delay_days'].mean()
    
    with col1:
        st.metric(
            label="📦 总订单数",
            value=f"{total_orders:,}",
            delta=None
        )
    
    with col2:
        st.metric(
            label="⏱️ 延迟率",
            value=f"{delay_rate:.1%}",
            delta=f"{delayed_orders} 延迟",
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            label="✅ 准时订单",
            value=f"{ontime_orders:,}",
            delta=f"{(1-delay_rate):.1%}"
        )
    
    with col4:
        st.metric(
            label="📅 平均延迟",
            value=f"{avg_delay:.1f} 天",
            delta="负数=提前"
        )
    
    st.markdown("---")
    
    # 图表区域
    col1, col2 = st.columns(2)
    
    with col1:
        # 延迟分布饼图
        st.subheader("订单延迟分布")
        delay_counts = df['is_delayed'].value_counts()
        fig = px.pie(
            values=delay_counts.values,
            names=['准时', '延迟'],
            title="",
            color_discrete_map={'准时': '#4caf50', '延迟': '#f44336'},
            hole=0.4
        )
        fig.update_traces(textposition='inside', textinfo='percent+label+value')
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 延迟天数分布
        st.subheader("延迟天数分布")
        fig = px.histogram(
            df,
            x='delay_days',
            nbins=40,
            title="",
            labels={'delay_days': '延迟天数', 'count': '订单数'},
            color_discrete_sequence=['#3498db']
        )
        fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="准时基准")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    # 月度趋势
    st.subheader("📅 月度延迟趋势")
    df['month'] = df['planned_start_date'].dt.to_period('M').astype(str)
    monthly_stats = df.groupby('month').agg({
        'is_delayed': ['count', 'sum', 'mean']
    }).reset_index()
    monthly_stats.columns = ['月份', '总订单', '延迟订单', '延迟率']
    monthly_stats['延迟率'] = monthly_stats['延迟率'] * 100
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_stats['月份'],
        y=monthly_stats['总订单'],
        name='总订单',
        marker_color='lightblue'
    ))
    fig.add_trace(go.Scatter(
        x=monthly_stats['月份'],
        y=monthly_stats['延迟率'],
        name='延迟率 (%)',
        yaxis='y2',
        marker_color='red',
        line=dict(width=3)
    ))
    
    fig.update_layout(
        yaxis=dict(title='订单数'),
        yaxis2=dict(title='延迟率 (%)', overlaying='y', side='right'),
        hovermode='x unified',
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Top物料
    st.subheader("🏆 生产量Top 10物料")
    top_materials = df.groupby('material')['order_quantity'].sum().sort_values(ascending=False).head(10)
    fig = px.bar(
        x=top_materials.index,
        y=top_materials.values,
        labels={'x': '物料', 'y': '总生产量'},
        color=top_materials.values,
        color_continuous_scale='Blues'
    )
    fig.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def show_model_performance(df, model):
    """模型性能页面"""
    st.header("📊 模型性能分析")
    
    # 准备数据
    engineer = APSFeatureEngineer()
    feature_names = engineer.get_feature_names()
    
    X = df[feature_names].values
    y_true = df['is_delayed'].values
    
    # 评估模型
    metrics = model.evaluate(X, y_true)
    
    # 性能指标
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
    
    st.markdown("---")
    
    # 混淆矩阵
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("混淆矩阵")
        cm = metrics['confusion_matrix']
        
        # 创建热力图
        fig = go.Figure(data=go.Heatmap(
            z=cm,
            x=['预测准时', '预测延迟'],
            y=['实际准时', '实际延迟'],
            text=cm,
            texttemplate='%{text}',
            colorscale='Blues',
            showscale=False
        ))
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # 详细统计
        tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
        st.info(f"""
        **真负例 (TN)**: {tn} - 正确预测准时  
        **假正例 (FP)**: {fp} - 误判为延迟  
        **假负例 (FN)**: {fn} - 漏判的延迟  
        **真正例 (TP)**: {tp} - 正确预测延迟
        """)
    
    with col2:
        st.subheader("Top 15 重要特征")
        
        importance = model.get_feature_importance()
        sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15]
        
        features = [f[0] for f in sorted_importance]
        importances = [f[1] for f in sorted_importance]
        
        fig = go.Figure(go.Bar(
            x=importances,
            y=features,
            orientation='h',
            marker=dict(
                color=importances,
                colorscale='Viridis'
            )
        ))
        fig.update_layout(
            height=500,
            yaxis={'categoryorder': 'total ascending'},
            xaxis_title="重要性分数"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 预测概率分布
    st.subheader("预测概率分布")
    y_proba = model.predict_proba(X)[:, 1]
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=y_proba[y_true == 0],
        name='实际准时',
        opacity=0.7,
        marker_color='green',
        nbinsx=50
    ))
    fig.add_trace(go.Histogram(
        x=y_proba[y_true == 1],
        name='实际延迟',
        opacity=0.7,
        marker_color='red',
        nbinsx=50
    ))
    
    fig.update_layout(
        barmode='overlay',
        xaxis_title='预测延迟概率',
        yaxis_title='订单数',
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)


def show_prediction(df, model):
    """实时预测页面"""
    st.header("🔮 实时预测演示")
    
    st.info("💡 从历史数据中随机选择订单进行预测演示")
    
    # 准备特征
    engineer = APSFeatureEngineer()
    feature_names = engineer.get_feature_names()
    
    X = df[feature_names].values
    y_true = df['is_delayed'].values
    
    # 随机选择10个订单
    np.random.seed(42)
    sample_indices = np.random.choice(len(df), min(10, len(df)), replace=False)
    
    for idx in sample_indices:
        row = df.iloc[idx]
        X_sample = X[idx:idx+1]
        
        # 预测
        prob = model.predict_proba(X_sample)[0, 1]
        pred = "延迟" if prob > 0.5 else "准时"
        actual = "延迟" if y_true[idx] == 1 else "准时"
        
        # 确定风险等级
        if prob >= 0.7:
            risk_class = "risk-high"
            risk_label = "🔴 高风险"
        elif prob >= 0.4:
            risk_class = "risk-medium"
            risk_label = "🟡 中风险"
        else:
            risk_class = "risk-low"
            risk_label = "🟢 低风险"
        
        with st.expander(f"订单 {row['production_number']} - {risk_label} ({prob:.1%})"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown(f"""
                **物料**: {row['material']}  
                **描述**: {row.get('material_description', 'N/A')[:40]}...  
                **数量**: {row['order_quantity']:.0f} 台  
                **产线**: {row['production_line']}  
                **计划开始**: {row['planned_start_date'].date()}
                """)
            
            with col2:
                # 仪表盘
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=prob * 100,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "延迟概率"},
                    gauge={
                        'axis': {'range': [None, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 40], 'color': "#e8f5e9"},
                            {'range': [40, 70], 'color': "#fff3e0"},
                            {'range': [70, 100], 'color': "#ffebee"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 70
                        }
                    }
                ))
                fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
            
            with col3:
                st.markdown(f"""
                **预测**: {pred}  
                **实际**: {actual}  
                **结果**: {'✅ 正确' if pred == actual else '❌ 错误'}
                """)
            
            # 建议
            if prob >= 0.7:
                st.error("🚨 **建议**: 立即介入，调整排程或增加资源")
            elif prob >= 0.4:
                st.warning("⚠️ **建议**: 加强监控，准备应急方案")
            else:
                st.success("✅ **建议**: 按计划执行，正常跟踪")


def show_risk_materials(df):
    """风险物料分析"""
    st.header("⚠️ 高风险物料识别")
    
    # 计算物料延迟统计
    material_stats = df.groupby('material').agg({
        'is_delayed': ['count', 'sum', 'mean'],
        'order_quantity': 'sum',
        'delay_days': 'mean'
    }).reset_index()
    
    material_stats.columns = ['物料', '总订单数', '延迟订单数', '延迟率', '总生产量', '平均延迟天数']
    
    # 筛选条件
    st.sidebar.markdown("### 筛选条件")
    min_orders = st.sidebar.slider("最少订单数", 1, 50, 10)
    min_delay_rate = st.sidebar.slider("最低延迟率", 0.0, 1.0, 0.2, 0.05)
    
    # 高风险物料
    high_risk = material_stats[
        (material_stats['总订单数'] >= min_orders) &
        (material_stats['延迟率'] >= min_delay_rate)
    ].sort_values('延迟率', ascending=False)
    
    st.subheader(f"发现 {len(high_risk)} 个高风险物料")
    
    if len(high_risk) > 0:
        # 展示表格（添加颜色标记）
        def color_delay_rate(val):
            if val >= 0.4:
                color = '#ffcdd2'  # 浅红
            elif val >= 0.25:
                color = '#fff9c4'  # 浅黄
            else:
                color = '#c8e6c9'  # 浅绿
            return f'background-color: {color}'
        
        # 格式化显示
        high_risk_display = high_risk.copy()
        high_risk_display['延迟率'] = high_risk_display['延迟率'].apply(lambda x: f"{x:.1%}")
        high_risk_display['平均延迟天数'] = high_risk_display['平均延迟天数'].apply(lambda x: f"{x:.1f}")
        
        st.dataframe(
            high_risk_display,
            use_container_width=True,
            height=400
        )
        
        # 可视化
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("延迟率排名")
            fig = px.bar(
                high_risk.head(10),
                x='延迟率',
                y='物料',
                orientation='h',
                color='延迟率',
                color_continuous_scale='Reds',
                labels={'延迟率': '延迟率'}
            )
            fig.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("订单量 vs 延迟率")
            fig = px.scatter(
                high_risk,
                x='总订单数',
                y='延迟率',
                size='总生产量',
                color='平均延迟天数',
                hover_data=['物料'],
                color_continuous_scale='RdYlGn_r'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("✅ 未发现符合条件的高风险物料")


def show_trends(df):
    """趋势分析"""
    st.header("📈 趋势分析")
    
    # 时间粒度选择
    time_grain = st.selectbox("选择时间粒度", ["周", "月", "季度"])
    
    if time_grain == "周":
        df['period'] = df['planned_start_date'].dt.to_period('W').astype(str)
    elif time_grain == "月":
        df['period'] = df['planned_start_date'].dt.to_period('M').astype(str)
    else:
        df['period'] = df['planned_start_date'].dt.to_period('Q').astype(str)
    
    # 聚合统计
    period_stats = df.groupby('period').agg({
        'is_delayed': ['count', 'sum', 'mean'],
        'delay_days': 'mean',
        'order_quantity': 'sum'
    }).reset_index()
    
    period_stats.columns = ['时间段', '总订单', '延迟订单', '延迟率', '平均延迟天数', '总生产量']
    period_stats['延迟率'] = period_stats['延迟率'] * 100
    
    # 趋势图
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("订单量趋势")
        fig = px.line(
            period_stats,
            x='时间段',
            y=['总订单', '延迟订单'],
            markers=True,
            labels={'value': '订单数', 'variable': '类型'}
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("延迟率趋势")
        fig = px.line(
            period_stats,
            x='时间段',
            y='延迟率',
            markers=True,
            labels={'延迟率': '延迟率 (%)'}
        )
        fig.add_hline(y=period_stats['延迟率'].mean(), line_dash="dash",
                     annotation_text=f"平均: {period_stats['延迟率'].mean():.1f}%")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    # 生产量与延迟关系
    st.subheader("生产负载 vs 延迟率")
    fig = px.scatter(
        period_stats,
        x='总生产量',
        y='延迟率',
        size='总订单',
        color='平均延迟天数',
        hover_data=['时间段'],
        color_continuous_scale='RdYlGn_r'
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # 详细表格
    st.subheader("详细统计数据")
    st.dataframe(period_stats, use_container_width=True, height=300)


if __name__ == "__main__":
    main()
