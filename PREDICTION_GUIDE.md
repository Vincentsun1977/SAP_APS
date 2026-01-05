# 📋 生产订单延迟预测 - 数据准备指南

## 🎯 目标
使用训练好的模型预测新生产订单的延迟风险

---

## 📊 需要提供的数据

### 方式1：完整数据文件（推荐）⭐

创建一个CSV文件，包含以下字段：

#### **必需字段**（来自订单系统）

| 字段名 | 说明 | 示例 | 来源 |
|--------|------|------|------|
| `Sales Order` | 销售订单号 | 504029252 | SAP订单 |
| `Sales Order Item` | 订单行项目 | 1001 | SAP订单 |
| `Order` | 生产订单号 | 1351101544 | SAP生产订单 |
| `Material Number` | 物料号 | CDX6090704R5012 | SAP物料主数据 |
| `Material description` | 物料描述 | VSC 7,2kV-400A 220V DCO | SAP物料主数据 |
| `Order quantity (GMEIN)` | 订单数量 | 5 | SAP订单 |
| `Basic start date` | 计划开始日期 | 2026-01-10 | SAP生产计划 |
| `Basic finish date` | 计划完成日期 | 2026-01-15 | SAP生产计划 |
| `Prodn Supervisor` | 生产监督员 | VSC | SAP |

#### **必需字段**（来自物料主数据 - FG.csv）

| 字段名 | 说明 | 示例 | 来源 |
|--------|------|------|------|
| `Production Line` | 生产线 | VSC | FG主数据 |
| `Total production Time` | 单位生产时长 | 2.5 | FG主数据 |
| `Constraint` | 生产约束 | 1.2 | FG主数据 |
| `earlist strart date` | 最早开工天数 | 3 | FG主数据 |

#### **必需字段**（来自产能数据 - Capacity.csv）

| 字段名 | 说明 | 示例 | 来源 |
|--------|------|------|------|
| `Capacity` | 产线日产能 | 10 | Capacity主数据 |

---

### 方式2：简化输入（最小数据集）

如果无法获取完整数据，至少需要以下核心字段：

| 字段名 | 说明 | 示例 |
|--------|------|------|
| `material` | 物料号 | CDX6090704R5012 |
| `order_quantity` | 订单数量 | 5 |
| `planned_start_date` | 计划开始日期 | 2026-01-10 |
| `planned_finish_date` | 计划完成日期 | 2026-01-15 |
| `production_line` | 生产线 | VSC |
| `total_production_time` | 单位生产时长 | 2.5 |
| `line_capacity` | 产线日产能 | 10 |

---

## 📁 **数据格式要求**

### CSV文件格式

**文件名**: `new_orders.csv` 或 `prediction_input.csv`

**编码**: UTF-8

**日期格式**: `YYYY-MM-DD` (例如: 2026-01-10)

**示例CSV内容**:
```csv
Sales Order,Sales Order Item,Order,Material Number,Material description,Order quantity (GMEIN),Basic start date,Basic finish date,Prodn Supervisor,Production Line,Total production Time,Constraint,earlist strart date,Capacity
504099999,1001,1351199999,CDX6090704R5012,VSC 7.2kV-400A 220V DCO Fixed Ver.,5,2026-01-10,2026-01-15,VSC,VSC,2.5,1.2,3,10
504099998,1001,1351199998,CDX6091204R5011,VSC 12kV-400A 220V SCO Fixed Ver.,3,2026-01-12,2026-01-16,VSC,VSC,2.3,1.1,2,10
```

---

## 🔧 **预测流程**

### 步骤1: 准备数据文件

将新订单数据保存为CSV文件，放在以下位置：
```
data/raw/new_orders.csv
```

### 步骤2: 运行预测脚本

我会为你创建一个预测脚本，使用方法：
```bash
python scripts/predict_new_orders.py --input data/raw/new_orders.csv --output predictions/results.csv
```

### 步骤3: 查看预测结果

输出文件会包含：
- 原始订单信息
- **延迟概率** (0-1之间)
- **预测结果** (0=准时, 1=延迟)
- **风险等级** (低/中/高)

---

## 📝 **数据获取建议**

### 从SAP系统导出

#### 1. 订单基础信息
```sql
-- SAP HANA/SQL查询示例
SELECT 
    vbak.vbeln AS "Sales Order",
    vbap.posnr AS "Sales Order Item",
    aufk.aufnr AS "Order",
    afpo.matnr AS "Material Number",
    makt.maktx AS "Material description",
    afpo.psmng AS "Order quantity (GMEIN)",
    afko.gstrp AS "Basic start date",
    afko.gltrp AS "Basic finish date",
    aufk.fevor AS "Prodn Supervisor"
FROM aufk
LEFT JOIN afko ON aufk.aufnr = afko.aufnr
LEFT JOIN afpo ON aufk.aufnr = afpo.aufnr
LEFT JOIN vbap ON afpo.kdauf = vbap.vbeln
LEFT JOIN makt ON afpo.matnr = makt.matnr
WHERE aufk.auart = 'PP01'  -- 生产订单类型
  AND afko.gstrp >= '2026-01-01'  -- 未来订单
```

#### 2. 物料主数据
从FG.csv或物料主数据表获取

#### 3. 产能数据
从Capacity.csv或产线配置表获取

---

## 🚀 **快速开始 - 使用示例数据**

我会为你创建：
1. ✅ **示例输入文件** - `data/sample/new_orders_example.csv`
2. ✅ **预测脚本** - `scripts/predict_new_orders.py`
3. ✅ **结果查看脚本** - `scripts/show_predictions.py`

---

## ⚠️ **注意事项**

### 1. 历史数据依赖
- 模型需要历史延迟率特征
- 新物料会使用全局平均值（准确度可能降低）
- **建议**: 至少有5-10个历史订单的物料预测更准确

### 2. 数据质量
- 确保日期格式正确
- 数量、产能等数值字段不能为空
- 物料号要与历史数据一致

### 3. 特征完整性
- 缺失字段会用默认值填充
- 但可能影响预测准确度

---

## 📞 **需要帮助？**

如果你有：
- ✅ SAP导出的Excel文件 → 我帮你转换
- ✅ 不完整的数据 → 我帮你补充默认值
- ✅ 特殊格式 → 我帮你适配

---

需要我现在为你创建预测脚本和示例文件吗？
