"""
可复用图表组件
"""
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, precision_recall_curve, auc


def render_confusion_matrix(cm, title="混淆矩阵", height=400):
    """渲染混淆矩阵热力图"""
    fig = go.Figure(data=go.Heatmap(
        z=cm,
        x=['预测准时', '预测延迟'],
        y=['实际准时', '实际延迟'],
        text=[[str(v) for v in row] for row in cm],
        texttemplate='%{text}',
        colorscale='Blues',
        showscale=False,
        hovertemplate='%{y} / %{x}: %{text}<extra></extra>'
    ))
    fig.update_layout(
        title=title,
        height=height,
        xaxis_title="预测",
        yaxis_title="实际",
        yaxis=dict(autorange='reversed')
    )
    return fig


def render_roc_curve(y_true, y_proba, title="ROC 曲线", height=400):
    """渲染ROC曲线"""
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    roc_auc = auc(fpr, tpr)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fpr, y=tpr,
        mode='lines',
        name=f'ROC (AUC={roc_auc:.3f})',
        line=dict(color='#1f77b4', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode='lines',
        name='随机基线',
        line=dict(color='gray', width=1, dash='dash')
    ))
    fig.update_layout(
        title=title,
        xaxis_title='假正率 (FPR)',
        yaxis_title='真正率 (TPR)',
        height=height,
        legend=dict(x=0.6, y=0.1)
    )
    return fig


def render_pr_curve(y_true, y_proba, title="Precision-Recall 曲线", height=400):
    """渲染PR曲线"""
    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    ap = auc(recall, precision)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=recall, y=precision,
        mode='lines',
        name=f'PR (AP={ap:.3f})',
        line=dict(color='#ff7f0e', width=2)
    ))
    baseline = y_true.sum() / len(y_true)
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[baseline, baseline],
        mode='lines',
        name=f'基线 ({baseline:.2f})',
        line=dict(color='gray', width=1, dash='dash')
    ))
    fig.update_layout(
        title=title,
        xaxis_title='召回率',
        yaxis_title='精确率',
        height=height,
        legend=dict(x=0.1, y=0.1)
    )
    return fig


def render_roc_comparison(results_dict, height=400):
    """渲染多模型ROC曲线对比"""
    fig = go.Figure()
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    for i, (name, (y_true, y_proba)) in enumerate(results_dict.items()):
        fpr, tpr, _ = roc_curve(y_true, y_proba)
        roc_auc = auc(fpr, tpr)
        fig.add_trace(go.Scatter(
            x=fpr, y=tpr,
            mode='lines',
            name=f'{name} (AUC={roc_auc:.3f})',
            line=dict(color=colors[i % len(colors)], width=2)
        ))
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode='lines', name='随机基线',
        line=dict(color='gray', width=1, dash='dash')
    ))
    fig.update_layout(
        title="ROC 曲线对比",
        xaxis_title='假正率 (FPR)',
        yaxis_title='真正率 (TPR)',
        height=height
    )
    return fig


def render_gauge(value, title="延迟概率", height=200):
    """渲染仪表盘"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value * 100,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        number={'suffix': '%'},
        gauge={
            'axis': {'range': [0, 100]},
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
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def render_feature_importance(importance_dict, top_n=15, height=500):
    """渲染特征重要性条形图"""
    sorted_imp = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]
    features = [f[0] for f in sorted_imp]
    values = [f[1] for f in sorted_imp]

    fig = go.Figure(go.Bar(
        x=values,
        y=features,
        orientation='h',
        marker=dict(color=values, colorscale='Viridis')
    ))
    fig.update_layout(
        title=f"Top {top_n} 重要特征",
        height=height,
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title="重要性分数"
    )
    return fig


def render_training_curves(train_metrics, val_metrics, metric_name="logloss", height=350):
    """渲染训练过程Loss曲线"""
    fig = go.Figure()
    epochs = list(range(1, len(train_metrics) + 1))

    fig.add_trace(go.Scatter(
        x=epochs, y=train_metrics,
        mode='lines', name=f'Train {metric_name}',
        line=dict(color='#1f77b4', width=2)
    ))
    if val_metrics:
        fig.add_trace(go.Scatter(
            x=epochs, y=val_metrics,
            mode='lines', name=f'Val {metric_name}',
            line=dict(color='#ff7f0e', width=2)
        ))
    fig.update_layout(
        title=f"训练过程 - {metric_name}",
        xaxis_title="轮次",
        yaxis_title=metric_name,
        height=height,
        hovermode='x unified'
    )
    return fig


def render_prediction_distribution(y_proba, y_true, height=350):
    """渲染预测概率分布"""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=y_proba[y_true == 0],
        name='实际准时', opacity=0.7,
        marker_color='#4caf50', nbinsx=50
    ))
    fig.add_trace(go.Histogram(
        x=y_proba[y_true == 1],
        name='实际延迟', opacity=0.7,
        marker_color='#f44336', nbinsx=50
    ))
    fig.update_layout(
        barmode='overlay',
        xaxis_title='预测延迟概率',
        yaxis_title='订单数',
        height=height,
        title="预测概率分布"
    )
    return fig


def render_metrics_over_time(metrics_df, metric_col='accuracy', time_col='period',
                              title="指标趋势", height=350):
    """渲染指标随时间变化趋势"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=metrics_df[time_col],
        y=metrics_df[metric_col],
        mode='lines+markers',
        name=metric_col,
        line=dict(width=2)
    ))
    mean_val = metrics_df[metric_col].mean()
    fig.add_hline(
        y=mean_val, line_dash="dash",
        annotation_text=f"平均: {mean_val:.3f}"
    )
    fig.update_layout(title=title, height=height, xaxis_title="时间", yaxis_title=metric_col)
    return fig


def render_sliced_heatmap(sliced_metrics_df, x_col='slice', y_col='metric',
                           value_col='value', title="分层评估热力图", height=400):
    """渲染分层评估热力图"""
    pivot = sliced_metrics_df.pivot(index=y_col, columns=x_col, values=value_col)
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale='RdYlGn',
        text=[[f"{v:.3f}" for v in row] for row in pivot.values],
        texttemplate='%{text}',
        hovertemplate='%{y} / %{x}: %{text}<extra></extra>'
    ))
    fig.update_layout(title=title, height=height)
    return fig
