# 🔮 如何使用模型预测新订单延迟风险

## ✅ **预测成功示例**

刚刚的预测结果：
- ✅ 处理了5个新订单
- ✅ 识别出1个高风险订单（延迟概率81%）
- ✅ 识别出1个中风险订单（延迟概率45.8%）
- ✅ 识别出3个低风险订单

---

## 📋 **需要提供的数据**

### 🎯 **最简单方式：复制现有订单格式**

参考示例文件：`data/sample/new_orders_example.csv`

**必需字段**：

```csv
Sales Order,Sales Order Item,Order,Material Number,Material description,Order quantity (GMEIN),Basic start date,Basic finish date,Prodn Supervisor,Production Line,Total production Time,Constraint,earlist strart date,Capacity
```

### 📊 **字段说明**

| 字段 | 中文名 | 示例 | 如何获取 |
|------|--------|------|----------|
| `Sales Order` | 销售订单号 | 504099999 | SAP销售订单 |
| `Sales Order Item` | 行项目 | 1001 | SAP销售订单 |
| `Order` | 生产订单号 | 1351199999 | SAP生产订单 |
| `Material Number` | 物料号 | CDX6090704R5012 | SAP物料主数据 |
| `Material description` | 物料描述 | VSC 7.2kV-400A... | SAP物料主数据 |
| `Order quantity (GMEIN)` | 订单数量 | 5 | SAP订单 |
| `Basic start date` | 计划开始日期 | 2026-01-10 | SAP生产计划 |
| `Basic finish date` | 计划完成日期 | 2026-01-15 | SAP生产计划 |
| `Prodn Supervisor` | 生产监督员 | VSC | SAP |
| `Production Line` | 生产线 | VSC | FG主数据 |
| `Total production Time` | 单位生产时长 | 2.5 | FG主数据 |
| `Constraint` | 生产约束 | 1.2 | FG主数据 |
| `earlist strart date` | 最早开工天数 | 3 | FG主数据 |
| `Capacity` | 产线日产能 | 10 | Capacity主数据 |

---

## 🚀 **预测步骤**

### 步骤1: 准备数据文件

**选项A: 从SAP导出**
1. 导出新的生产订单（未开始的订单）
2. 保存为Excel或CSV格式
3. 确保包含上述必需字段

**选项B: 手动创建**
1. 复制 `data/sample/new_orders_example.csv`
2. 修改为你的实际订单数据
3. 保存到 `data/raw/new_orders.csv`

### 步骤2: 运行预测

```bash
# 使用默认示例文件
python scripts\predict_new_orders.py

# 或指定你的文件
python scripts\predict_new_orders.py --input data\raw\new_orders.csv --output predictions\my_predictions.csv
```

### 步骤3: 查看结果

预测结果会保存到 `predictions/` 目录，包含：

| 输出字段 | 说明 | 示例 |
|---------|------|------|
| 销售订单 | 原始订单号 | 504099999 |
| 物料号 | 物料编号 | CDX6090704R5012 |
| 物料描述 | 物料名称 | VSC 7.2kV-400A... |
| 订单数量 | 数量 | 5 |
| 计划开始日期 | 开始日期 | 2026-01-10 |
| 计划完成日期 | 完成日期 | 2026-01-15 |
| **延迟概率(%)** | 延迟可能性 | **81.0%** 🎯 |
| **预测结果** | 0=准时, 1=延迟 | **1** 🎯 |
| **风险等级** | 低/中/高 | **高风险** 🎯 |

---

## 📊 **风险等级定义**

| 风险等级 | 延迟概率范围 | 建议行动 |
|---------|-------------|----------|
| 🟢 **低风险** | 0% - 30% | 正常排程，定期监控 |
| 🟡 **中风险** | 30% - 70% | 重点关注，准备应急方案 |
| 🔴 **高风险** | 70% - 100% | 立即采取行动，优先处理 |

---

## 💡 **实际应用建议**

### 1️⃣ **定期预测**
```bash
# 每周一预测本周订单
python scripts\predict_new_orders.py --input weekly_orders.csv
```

### 2️⃣ **重点关注高风险订单**
- 延迟概率 > 70% 的订单
- 提前协调资源
- 与客户沟通调整交期

### 3️⃣ **分析延迟原因**
查看高风险订单的特征：
- 物料历史延迟率高？
- 订单数量过大？
- 生产复杂度高？
- 产能不足？

### 4️⃣ **持续改进**
- 记录预测结果和实际结果
- 定期重新训练模型
- 更新历史数据

---

## 🔧 **数据准备技巧**

### 技巧1: 如果缺少某些字段

**缺少物料主数据字段**：
- 系统会自动从 `FG.csv` 匹配
- 确保物料号在FG.csv中存在

**缺少产能数据**：
- 系统会自动从 `Capacity.csv` 匹配
- 确保生产线在Capacity.csv中存在

### 技巧2: Excel转CSV

如果你有Excel文件：
```bash
python convert_excel_to_csv.py
```

### 技巧3: 批量预测

准备多个订单在一个CSV文件中，一次性预测：
```csv
Sales Order,Material Number,Order quantity (GMEIN),Basic start date,Basic finish date,...
504099999,CDX6090704R5012,5,2026-01-10,2026-01-15,...
504099998,CDX6091204R5011,3,2026-01-12,2026-01-16,...
504099997,CDX6090704R5012,8,2026-01-15,2026-01-20,...
...
```

---

## 📝 **完整示例**

### 示例1: 预测单个订单

**输入文件** (`my_order.csv`):
```csv
Sales Order,Sales Order Item,Order,Material Number,Material description,Order quantity (GMEIN),Basic start date,Basic finish date,Prodn Supervisor,Production Line,Total production Time,Constraint,earlist strart date,Capacity
504100000,1001,1351200000,CDX6090704R5012,VSC 7.2kV-400A 220V DCO Fixed Ver.,10,2026-01-25,2026-02-05,VSC,VSC,2.5,1.2,3,10
```

**运行预测**:
```bash
python scripts\predict_new_orders.py --input my_order.csv --output my_prediction.csv
```

**输出结果**:
```
延迟概率: 75.3%
风险等级: 高风险
建议: 立即采取行动
```

---

## ⚠️ **注意事项**

### 1. 历史数据要求
- ✅ 模型依赖历史延迟率特征
- ✅ 物料在历史数据中出现过 → 预测更准确
- ⚠️ 全新物料 → 使用全局平均值（准确度降低）

### 2. 数据质量
- ✅ 日期格式：`YYYY-MM-DD` (如 2026-01-10)
- ✅ 数值字段不能为空
- ✅ 物料号要与历史数据一致

### 3. 预测时效性
- ✅ 建议每周重新训练模型
- ✅ 使用最新历史数据
- ✅ 保持数据更新

---

## 🎯 **预测结果解读**

### 示例结果分析

**订单1**: 物料 CDX6090704R5012, 数量5
- **延迟概率**: 81.0% 🔴
- **风险等级**: 高风险
- **原因分析**:
  - 该物料历史延迟率较高
  - 订单数量适中
  - 计划在周五开始（周末影响）

**建议行动**:
1. ✅ 提前备料
2. ✅ 协调产线资源
3. ✅ 与客户沟通可能延迟
4. ✅ 考虑提前开工

---

## 📞 **快速参考**

### 命令速查

```bash
# 1. 预测示例订单
python scripts\predict_new_orders.py

# 2. 预测你的订单
python scripts\predict_new_orders.py --input data\raw\new_orders.csv

# 3. 指定输出位置
python scripts\predict_new_orders.py --input my_orders.csv --output results\predictions.csv

# 4. 查看帮助
python scripts\predict_new_orders.py --help
```

### 文件位置

- **输入示例**: `data/sample/new_orders_example.csv`
- **预测脚本**: `scripts/predict_new_orders.py`
- **输出目录**: `predictions/`
- **模型文件**: `models/aps_xgb_model_optimized_*.pkl`

---

## 🎓 **总结**

### ✅ 你需要提供：
1. **CSV文件** - 包含新订单信息
2. **14个必需字段** - 订单、物料、计划、产能信息
3. **正确的日期格式** - YYYY-MM-DD

### ✅ 你会得到：
1. **延迟概率** - 0-100%的延迟可能性
2. **风险等级** - 低/中/高风险分类
3. **预测结果** - 是否会延迟
4. **详细报告** - CSV格式，可导入Excel

### ✅ 使用建议：
- 🎯 重点关注高风险订单（>70%）
- 📊 定期预测，持续监控
- 🔄 结合人工经验判断
- 📈 记录预测准确度，持续改进

---

需要帮助准备你的实际订单数据吗？
