# 生产环境部署指南

## 🚀 如何将模型用于生产数据预测

### 📋 部署步骤总览

1. **模型部署** - 将训练好的模型部署到生产环境
2. **数据准备** - 准备新订单数据
3. **预测执行** - 运行预测脚本
4. **结果应用** - 根据预测结果采取行动

---

## 1️⃣ 模型部署方式

### 方式A: 批量预测（离线）

**适用场景**: 每天/每周处理一批新订单

```bash
# 每天定时运行
python scripts/predict_production.py
```

### 方式B: 实时API服务（在线）

**适用场景**: 订单创建时实时预测

```bash
# 启动API服务
python src/api/prediction_service.py
```

### 方式C: Dashboard集成

**适用场景**: 用户通过Dashboard上传订单预测

```bash
# 已集成在Streamlit Dashboard中
streamlit run streamlit_app/aps_dashboard.py
```

---

## 2️⃣ 批量预测使用方法

### 步骤1: 准备新订单数据

创建CSV文件 `new_orders.csv`，包含以下字段：

```csv
production_number,sales_doc,material,order_quantity,planned_start_date,production_line,supervisor
P2026001,S001,CDX6291204R5011,10,2026-02-01,VSC,John
P2026002,S002,CDX6291204R5012,5,2026-02-05,VSC,Mary
```

**必需字段**:
- production_number（生产订单号）
- material（物料号）
- order_quantity（订单数量）
- planned_start_date（计划开始日期）
- production_line（产线）

### 步骤2: 运行预测脚本

```bash
cd /opt/sap-production-predictor
source venv/bin/activate

python scripts/predict_production.py \
  --input data/new_orders/orders_2026_01.csv \
  --model models/aps_xgb_model_20251224_194431.json \
  --output predictions/pred_2026_01.csv
```

### 步骤3: 查看预测结果

```csv
production_number,material,delay_probability,prediction,risk_level,recommendation
P2026001,CDX6291204R5011,0.78,1,高风险,🚨 立即采取行动
P2026002,CDX6291204R5012,0.23,0,低风险,✅ 按计划执行
```

---

## 3️⃣ 单个订单实时预测

### Python代码示例

```python
from scripts.predict_production import predict_single_order

# 单个订单数据
order = {
    'production_number': 'P2026001',
    'material': 'CDX6291204R5011',
    'order_quantity': 15,
    'planned_start_date': '2026-02-01',
    'total_production_time': 2.5,
    'line_capacity': 50,
    'constraint': 1.2,
}

# 预测
result = predict_single_order(
    order_data=order,
    model_path='models/aps_xgb_model.json'
)

# 结果
print(f"延迟概率: {result['delay_probability']:.1%}")
print(f"风险等级: {result['risk_level']}")
print(f"建议: {result['recommendation']}")

# 输出:
# 延迟概率: 78.5%
# 风险等级: 高风险
# 建议: 🚨 立即采取行动：调配额外资源，调整排程
```

---

## 4️⃣ API服务部署

### 创建API服务

```python
# src/api/prediction_service.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Order(BaseModel):
    production_number: str
    material: str
    order_quantity: int
    planned_start_date: str

@app.post("/predict")
def predict_delay(order: Order):
    result = predict_single_order(order.dict(), MODEL_PATH)
    return {
        "order_id": order.production_number,
        "delay_probability": result['delay_probability'],
        "risk_level": result['risk_level'],
        "recommendation": result['recommendation']
    }
```

### 启动API

```bash
uvicorn src.api.prediction_service:app --host 0.0.0.0 --port 8000
```

### 调用API

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "production_number": "P2026001",
    "material": "CDX6291204R5011",
    "order_quantity": 15,
    "planned_start_date": "2026-02-01"
  }'
```

响应:
```json
{
  "order_id": "P2026001",
  "delay_probability": 0.785,
  "risk_level": "高风险",
  "recommendation": "🚨 立即采取行动：调配额外资源，调整排程"
}
```

---

## 5️⃣ 自动化预测流程

### 使用Cron定时任务

```bash
# 编辑crontab
crontab -e

# 每天早上8点预测当天新订单
0 8 * * * cd /opt/sap-production-predictor && ./predict_daily.sh

# 每周一早上预测本周订单
0 8 * * 1 cd /opt/sap-production-predictor && ./predict_weekly.sh
```

### 预测脚本示例

```bash
#!/bin/bash
# predict_daily.sh

DATE=$(date +%Y%m%d)
INPUT="data/new_orders/orders_${DATE}.csv"
OUTPUT="predictions/pred_${DATE}.csv"
MODEL="models/aps_xgb_model_latest.json"

python scripts/predict_production.py \
  --input $INPUT \
  --model $MODEL \
  --output $OUTPUT

# 发送高风险订单告警邮件
python scripts/send_alert_email.py \
  --predictions $OUTPUT \
  --threshold 0.7
```

---

## 6️⃣ 预测结果应用

### 风险等级与行动建议

| 风险等级 | 延迟概率 | 建议行动 |
|---------|---------|----------|
| 🔴 **高风险** | ≥70% | 立即行动：调整排程、增加资源、沟通客户 |
| 🟡 **中风险** | 40-70% | 密切监控：准备应急预案、提前协调 |
| 🟢 **低风险** | <40% | 正常跟踪：按计划执行、定期复核 |

### 集成到生产系统

1. **SAP系统集成**
   - 通过RFC/BAPI将预测结果写回SAP
   - 在生产订单上添加"延迟风险"字段
   - 触发工作流审批高风险订单

2. **邮件/消息告警**
   - 高风险订单自动发送邮件给相关人员
   - 企业微信/钉钉推送通知
   - Dashboard红色预警显示

3. **排程系统优化**
   - 根据风险等级调整优先级
   - 自动为高风险订单预留产能
   - 建议最优排程方案

---

## 7️⃣ 模型更新和维护

### 定期重新训练

```bash
# 每月更新模型（使用最新历史数据）
python scripts/train_aps_model.py \
  --data data/history/history_$(date +%Y%m).csv \
  --output models/aps_xgb_model_$(date +%Y%m%d).json
```

### A/B测试

```python
# 同时运行新旧模型
pred_old = predict(X, model_v1)
pred_new = predict(X, model_v2)

# 比较性能
compare_metrics(pred_old, pred_new, y_true)
```

### 监控模型性能

```python
# 定期评估预测准确性
actual_delays = get_actual_finished_orders()
predictions = get_historical_predictions()

accuracy = calculate_accuracy(predictions, actual_delays)

if accuracy < 0.85:
    send_alert("模型性能下降，需要重新训练")
```

---

## 8️⃣ 生产环境检查清单

### 部署前检查

- [ ] 模型文件已部署到生产服务器
- [ ] Python环境和依赖已安装
- [ ] 数据源连接正常（CSV/数据库）
- [ ] 训练数据和模型版本一致
- [ ] 预测脚本测试通过
- [ ] 日志记录配置完成
- [ ] 错误处理机制就位
- [ ] 性能测试完成（预测速度）

### 运行时监控

- [ ] 预测请求量
- [ ] 平均响应时间
- [ ] 错误率
- [ ] 高风险订单占比
- [ ] 模型准确率（定期回测）

---

## 💡 最佳实践

1. **数据质量**
   - 确保新订单数据格式与训练数据一致
   - 处理缺失值和异常值
   - 验证必需字段完整性

2. **性能优化**
   - 批量预测优于单条
   - 使用缓存存储FG/Capacity数据
   - 异步处理大批量请求

3. **错误处理**
   - 记录所有预测请求和结果
   - 对异常情况降级处理
   - 提供人工审核接口

4. **版本管理**
   - 模型文件命名包含日期版本
   - 保留最近3个版本用于回滚
   - 记录每个版本的性能指标

---

## 📞 技术支持

预测失败常见原因：
- 新订单缺少必需字段
- 特征值超出训练范围
- 模型文件损坏或版本不匹配
- 内存不足（大批量预测）

查看日志: `/opt/sap-production-predictor/logs/prediction.log`
