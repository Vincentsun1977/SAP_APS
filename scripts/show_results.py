"""
Simple demo script to showcase APS model training results
展示APS模型训练结果 (无需matplotlib)
"""
import sys
sys.path.append('.')

import pandas as pd
import numpy as np
from src.models.xgboost_model import ProductionDelayModel
from src.data_processing.aps_feature_engineer import APSFeatureEngineer

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_bar_chart(data, max_width=50):
    """打印文本柱状图"""
    max_val = max(data.values())
    for label, value in data.items():
        bar_width = int((value / max_val) * max_width)
        bar = '█' * bar_width
        print(f"  {label:20s} |{bar} {value:.0f}")

print_header("🚀 SAP生产延迟预测模型 - 训练结果展示")

# 1. 加载训练数据
print("\n📊 正在加载训练数据...")
try:
    df = pd.read_csv("data/processed/aps_training_data_full.csv")
    print(f"   ✓ 成功加载 {len(df):,} 条历史生产订单")
    
    # 解析日期
    df['planned_start_date'] = pd.to_datetime(df['planned_start_date'])
    date_min = df['planned_start_date'].min().strftime('%Y-%m-%d')
    date_max = df['planned_start_date'].max().strftime('%Y-%m-%d')
    print(f"   ✓ 数据时间范围: {date_min} 至 {date_max}")
except Exception as e:
    print(f"   ✗ 加载失败: {e}")
    sys.exit(1)

# 2. 基本统计
print_header("📈 数据统计概览")

total_orders = len(df)
delayed_orders = df['is_delayed'].sum()
ontime_orders = total_orders - delayed_orders
delay_rate = delayed_orders / total_orders
avg_delay = df['delay_days'].mean()
max_delay = df['delay_days'].max()
min_delay = df['delay_days'].min()

print(f"""
   总订单数量: {total_orders:,} 条
   
   延迟订单数: {delayed_orders:,} 条 ({delay_rate:.1%})
   准时订单数: {ontime_orders:,} 条 ({1-delay_rate:.1%})
   
   平均延迟:   {avg_delay:+.2f} 天 (负数表示提前)
   最大延迟:   {max_delay:+.0f} 天
   最小延迟:   {min_delay:+.0f} 天
""")

# 3. Top材料
print_header("🏆 生产量Top 5物料")
top_materials = df.groupby('material')['order_quantity'].sum().sort_values(ascending=False).head(5)
print()
for i, (material, qty) in enumerate(top_materials.items(), 1):
    print(f"   {i}. {material:20s}  {qty:6.0f} 台")

# 4. 产线统计
print_header("🏭 各产线统计")
line_stats = df.groupby('production_line').agg({
    'is_delayed': ['count', 'sum', 'mean']
}).round(3)

print(f"\n   {'产线':10s} | {'总订单':>8s} | {'延迟订单':>8s} | {'延迟率':>8s}")
print("   " + "-" * 45)
for line, row in line_stats.iterrows():
    total = int(row[('is_delayed', 'count')])
    delayed = int(row[('is_delayed', 'sum')])
    rate = row[('is_delayed', 'mean')]
    print(f"   {line:10s} | {total:8d} | {delayed:8d} | {rate:7.1%}")

# 5. 加载模型
print_header("🤖 加载训练模型")

model_path = "models/aps_xgb_model_20251224_194431.json"
try:
    model = ProductionDelayModel()
    model.load(model_path)
    print(f"   ✓ 模型加载成功")
    print(f"   ✓ 模型路径: {model_path}")
except Exception as e:
    print(f"   ✗ 模型加载失败: {e}")
    sys.exit(1)

# 6. 特征重要性
print_header("🎯 Top 15 最重要的预测特征")

feature_engineer = APSFeatureEngineer()
feature_names = feature_engineer.get_feature_names()
model.feature_names = feature_names

importance = model.get_feature_importance()
sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)

# 特征名称中文映射
feature_cn_map = {
    'material_delay_rate_90d': '物料90天历史延迟率',
    'planned_start_quarter': '计划开始季度',
    'planned_start_weekday': '计划开始星期',
    'complexity_capacity_interaction': '复杂度×产能交互',
    'qty_time_interaction': '数量×时间交互',
    'planned_duration_days': '计划生产天数',
    'expected_production_days': '预期生产天数',
    'line_delay_rate_90d': '产线90天历史延迟率',
    'production_time_category_encoded': '生产时长类别',
    'week_of_year': '年度第几周',
    'planned_start_month': '计划开始月份',
    'order_quantity': '订单数量',
    'material_family_delay_rate': '物料族历史延迟率',
    'is_large_order': '是否大订单',
    'production_complexity': '生产复杂度'
}

print(f"\n   {'排名':>4s} | {'特征名称':38s} | {'重要性':>8s} | 重要性可视化")
print("   " + "-" * 85)

for i, (feat, imp) in enumerate(sorted_importance[:15], 1):
    feat_cn = feature_cn_map.get(feat, feat[:35])
    bar_width = int(imp * 100)
    bar = '█' * min(bar_width, 40)
    print(f"   {i:4d} | {feat_cn:38s} | {imp:8.4f} | {bar}")

# 7. 模型性能评估
print_header("📊 模型性能指标")

X = df[feature_names].values
y_true = df['is_delayed'].values

metrics = model.evaluate(X, y_true)

print(f"""
   准确率 (Accuracy):  {metrics['accuracy']:.2%}  
   精确率 (Precision): {metrics['precision']:.2%}  - 预测为延迟时的正确率
   召回率 (Recall):    {metrics['recall']:.2%}  - 实际延迟被识别出的比例
   F1分数 (F1 Score):  {metrics['f1_score']:.4f}
   ROC AUC:            {metrics['roc_auc']:.4f}
""")

print("   混淆矩阵:")
cm = metrics['confusion_matrix']
print(f"""
                    预测准时      预测延迟
   实际准时         {cm[0][0]:6d}        {cm[0][1]:6d}
   实际延迟         {cm[1][0]:6d}        {cm[1][1]:6d}
""")

# 计算额外指标
tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
specificity = tn / (tn + fp)
npv = tn / (tn + fn) if (tn + fn) > 0 else 0

print(f"   特异性 (Specificity): {specificity:.2%}  - 实际准时被正确识别的比例")
print(f"   阴性预测值 (NPV):     {npv:.2%}  - 预测准时实际准时的比例")

# 8. 预测示例
print_header("🔮 预测示例 - 随机抽取10个订单")

np.random.seed(42)
sample_indices = np.random.choice(len(df), min(10, len(df)), replace=False)

print(f"\n   {'物料ID':17s} | {'数量':>4s} | {'计划日期':10s} | {'实际':4s} | {'预测概率':>8s} | {'预测':4s} | 结果")
print("   " + "-" * 80)

correct_count = 0
for idx in sample_indices:
    material = df.iloc[idx]['material'][:17]
    qty = df.iloc[idx]['order_quantity']
    planned_date = df.iloc[idx]['planned_start_date'].strftime('%Y-%m-%d')
    actual = "延迟" if y_true[idx] == 1 else "准时"
    
    # 预测
    X_sample = X[idx:idx+1]
    prob = model.predict_proba(X_sample)[0, 1]
    pred = "延迟" if prob > 0.5 else "准时"
    
    # 判断结果
    if actual == pred:
        correct = "✓ 正确"
        correct_count += 1
    else:
        correct = "✗ 错误"
    
    print(f"   {material:17s} | {qty:4.0f} | {planned_date} | {actual:4s} | {prob:7.1%} | {pred:4s} | {correct}")

print(f"\n   样本预测准确率: {correct_count}/{len(sample_indices)} = {correct_count/len(sample_indices):.1%}")

# 9. 按季度统计
print_header("📅 各季度延迟率统计")

df['quarter'] = df['planned_start_date'].dt.to_period('Q')
quarterly_stats = df.groupby('quarter').agg({
    'is_delayed': ['count', 'sum', 'mean']
}).round(3)

print(f"\n   {'季度':8s} | {'总订单':>8s} | {'延迟订单':>8s} | {'延迟率':>8s}")
print("   " + "-" * 45)
for quarter, row in quarterly_stats.iterrows():
    total = int(row[('is_delayed', 'count')])
    delayed = int(row[('is_delayed', 'sum')])
    rate = row[('is_delayed', 'mean')]
    print(f"   {str(quarter):8s} | {total:8d} | {delayed:8d} | {rate:7.1%}")

# 10. 高风险物料识别
print_header("⚠️  高风险物料识别 (延迟率>20%且订单量>10)")

material_risk = df.groupby('material').agg({
    'is_delayed': ['count', 'sum', 'mean']
}).round(3)

high_risk = material_risk[
    (material_risk[('is_delayed', 'count')] > 10) &
    (material_risk[('is_delayed', 'mean')] > 0.20)
].sort_values(by=('is_delayed', 'mean'), ascending=False)

if len(high_risk) > 0:
    print(f"\n   {'物料ID':20s} | {'总订单':>8s} | {'延迟订单':>8s} | {'延迟率':>8s}")
    print("   " + "-" * 57)
    for material, row in high_risk.head(10).iterrows():
        total = int(row[('is_delayed', 'count')])
        delayed = int(row[('is_delayed', 'sum')])
        rate = row[('is_delayed', 'mean')]
        print(f"   {material:20s} | {total:8d} | {delayed:8d} | {rate:7.1%}")
else:
    print("\n   ✓ 未发现高风险物料")

# 11. 总结
print_header("✨ 训练结果总结")

print(f"""
   ✅ 训练数据规模: {total_orders:,} 条历史订单
   ✅ 特征工程:     {len(feature_names)} 个预测特征
   ✅ 模型准确率:   {metrics['accuracy']:.1%}
   ✅ ROC AUC:      {metrics['roc_auc']:.3f}
   ✅ 数据延迟率:   {delay_rate:.1%}
   
   🎯 模型可用于:
      • 新订单延迟风险预测
      • 高风险物料识别
      • 生产排程优化建议
      • 产能瓶颈分析
   
   📁 相关文件:
      • 模型文件: {model_path}
      • 训练数据: data/processed/aps_training_data_full.csv
      • 训练脚本: scripts/train_aps_model.py
""")

print("=" * 80)
print("  演示完成！模型已ready，可用于生产环境预测。")
print("=" * 80)
