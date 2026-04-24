# APS生产时长预测系统 - 特征与标签说明（v2）

> **版本说明**：v2模型（2026-04）已从"是否延迟"二分类升级为"实际生产天数"回归预测，消除了数据泄露，引入缺料数据，全面提升预测质量。

## 📊 数据结构概览

### 原始数据来源（6个CSV文件）

1. **History.csv** - 历史生产订单（主数据源，2,491条）
2. **Order.csv** - 客户订单需求
3. **FG.csv** - 成品物料主数据
4. **Capacity.csv** - 产线产能
5. **APS.csv** - APS生产计划
6. **Shortage.csv** - 物料缺料数据（SAP MM/PP导出，300,872条组件记录）

---

## 🎯 标签（Label）- 预测目标

### `actual_production_days` - 实际生产天数（回归）

**定义：**
```python
actual_production_days = (actual_finish_date - created_date).days
```

**取值范围（训练集，过滤离群值后）：**
- 最小：0 天
- 最大：23 天
- 均值：2.95 天
- 中位数：2 天
- 标准差：2.27 天

**来源：**
```
actual_finish_date (History.csv "Actual finish date")
created_date       (History.csv "Created on")
```

**离群值过滤（v2）：**
- 移除 `actual_production_days > 30` 的样本（极端值）
- 移除 `order_quantity > 500` 的样本（异常大单）
- 过滤后：2,487 条有效样本（原始 2,491）

**预测用途：**
```
预测的 actual_production_days → 与 planned_finish_date 对比 → 延迟风险判断
若 actual_start_date + predicted_days > planned_finish_date → 判定高风险
```

> ⚠️ **v1废弃标签说明**：旧版使用 `is_delayed`（二分类），因其依赖 `actual_finish_date` 造成数据泄露，已从特征集中完全移除。

---

## 🔍 特征（Features）- 54个预测特征

### ❌ 已移除的泄露特征（v2 P0修复）

| 特征名 | 移除原因 |
|--------|---------|
| `actual_duration_days` | 依赖实际完成日期，预测时未知 |
| `delay_days` | 依赖实际完成日期，预测时未知 |
| `is_delayed` | 依赖实际完成日期，预测时未知 |
| `production_line_encoded` | 常量特征（只有VSC一条产线） |
| `line_capacity` | 常量特征（固定值15） |
| `has_supervisor` | 常量特征（始终为True） |

---

### 特征分类

#### 1️⃣ 基础订单特征（8个）

| 特征名 | 说明 | 数据来源 | 类型 |
|--------|------|----------|------|
| `order_quantity` | 订单数量 | History.csv | 数值 |
| `planned_duration_days` | 计划生产天数 | planned_finish - planned_start | 数值 |
| `constraint_factor` | 生产约束系数 | FG.csv (Constraint) | 数值 |
| `earliest_start_days` | 最早开工等待天数 | FG.csv | 数值 |
| `total_production_time` | 单位生产时长（工时/件） | FG.csv | 数值 |
| `qty_capacity_ratio` | 数量/产能比 | order_quantity / line_capacity | 数值 |
| `expected_production_days` | 预计生产天数 | qty × time / capacity | 数值 |
| `log_order_quantity` | 订单量对数变换（v2新增） | log1p(order_quantity) | 数值 |

#### 2️⃣ 时间特征（11个）

| 特征名 | 说明 | 类型 |
|--------|------|------|
| `planned_start_month` | 计划开始月份 | 数值(1-12) |
| `planned_start_weekday` | 计划开始星期 | 数值(0-6) |
| `planned_start_quarter` | 计划开始季度 | 数值(1-4) |
| `planned_start_day_of_month` | 月内第几天 | 数值(1-31) |
| `planned_start_is_weekend` | 是否周末开工 | 二值(0/1) |
| `planned_start_is_month_start` | 是否月初（≤5日） | 二值(0/1) |
| `planned_start_is_month_end` | 是否月末（≥25日） | 二值(0/1) |
| `planned_finish_month` | 计划完成月份 | 数值(1-12) |
| `planned_finish_quarter` | 计划完成季度 | 数值(1-4) |
| `planned_finish_weekday` | 计划完成星期 | 数值(0-6) |
| `planned_production_days` | 计划生产天数（日历） | 数值 |

#### 3️⃣ 物料与复杂度特征（5个）

| 特征名 | 说明 | 类型 |
|--------|------|------|
| `material_complexity` | 物料生产复杂度（time × constraint） | 数值 |
| `is_high_constraint` | 是否高约束物料（v2新增） | 二值(0/1) |
| `is_large_order` | 是否大订单（qty > 10） | 二值(0/1) |
| `mrp_controller_encoded` | MRP控制员编码（v2新增） | 数值 |
| `expected_production_time` | 预期生产工时 | 数值 |

#### 4️⃣ 并发工作负载特征（4个）- v2新增

| 特征名 | 说明 | 类型 |
|--------|------|------|
| `create_to_start_gap` | 创建到计划开始间隔天数 | 数值 |
| `concurrent_orders_on_start` | 计划开始日并发订单数 | 数值 |
| `concurrent_qty_on_start` | 计划开始日并发总数量 | 数值 |
| `qty_share_of_day` | 本订单占当日产能份额 | 数值(0-1) |

#### 5️⃣ 历史生产时长特征（7个）- v2升级

| 特征名 | 说明 | 计算方式 | 类型 |
|--------|------|----------|------|
| `material_avg_production_time_90d` | 物料90天平均生产时长 | 因果扩展均值 | 数值 |
| `material_std_production_time_90d` | 物料90天生产时长标准差 | 扩展计算 | 数值 |
| `material_max_production_time_90d` | 物料90天最大生产时长 | 扩展计算 | 数值 |
| `material_order_count_30d` | 30天内同物料下单次数 | 滚动计数 | 数值 |
| `material_last_production_time` | 上次实际生产时长 | 前值 | 数值 |
| `line_avg_production_time_90d` | 产线90天平均生产时长 | 因果扩展均值 | 数值 |
| `material_line_avg_production_time_90d` | 物料×产线90天均值 | 因果扩展均值 | 数值 |

> ⚠️ **v2关键修复**：历史特征使用**因果扩展均值**（expanding mean），确保每个样本仅使用其之前的历史数据，避免未来数据泄露。

#### 6️⃣ 目标编码（1个）- v2新增

| 特征名 | 说明 | 类型 |
|--------|------|------|
| `material_target_encoded` | 物料的因果平均生产时长（目标编码） | 数值 |

#### 7️⃣ 缺料特征（7个）- 来自 Shortage.csv

| 特征名 | 说明 | 类型 |
|--------|------|------|
| `has_shortage` | 是否存在缺料组件 | 二值(0/1) |
| `shortage_component_count` | 缺料组件数量 | 数值 |
| `total_shortage_qty` | 缺料总量 | 数值 |
| `max_shortage_qty` | 最大单组件缺料量 | 数值 |
| `max_shortage_pct` | 最大缺料占需求比例 | 数值(0-1) |
| `shortage_component_ratio` | 缺料组件占总组件数比例（v2新增） | 数值(0-1) |
| `shortage_qty_ratio` | 缺料总量占总需求比例（v2新增） | 数值(0-1) |

#### 8️⃣ 产能与工作强度特征（3个）

| 特征名 | 说明 | 类型 |
|--------|------|------|
| `capacity_utilization` | 当日产能利用率 | 数值(0-1) |
| `total_capacity_available` | 可用总产能 | 数值 |
| `workload_intensity` | 工作强度指数 | 数值 |

#### 9️⃣ 交互特征（8个）

| 特征名 | 说明 | 计算方式 |
|--------|------|----------|
| `complexity_capacity_interaction` | 复杂度 × 产能比 | material_complexity × qty_capacity_ratio |
| `qty_time_interaction` | 数量 × 时间 | order_quantity × total_production_time |
| `constraint_qty_interaction` | 约束 × 数量 | constraint_factor × order_quantity |
| `expected_planned_ratio` | 预期/计划天数比 | expected_production_days / planned_production_days |
| `shortage_qty_interaction` | 缺料量 × 订单量 | total_shortage_qty × order_quantity |
| `shortage_complexity_interaction` | 缺料率 × 复杂度 | max_shortage_pct × material_complexity |
| `shortage_ratio_qty_interaction` | 缺料比例 × 订单量（v2新增） | shortage_component_ratio × order_quantity |
| `qty_per_planned_day` | 单日计划产量 | order_quantity / planned_production_days |

---

## 📈 特征重要性排名（Top 15，v2最新）

训练日期：2026-04-15 | 数据：2,487条 | 模型：XGBoost Regressor

| 排名 | 特征 | 重要性 | 类别 |
|------|------|--------|------|
| 1 | `earliest_start_days` | 0.1826 | 基础特征 ⭐ |
| 2 | `total_production_time` | 0.1367 | 基础特征 |
| 3 | `create_to_start_gap` | 0.1331 | 并发负载 ⭐ |
| 4 | `shortage_qty_ratio` | 0.0576 | 缺料特征 ⭐ |
| 5 | `shortage_component_count` | 0.0294 | 缺料特征 |
| 6 | `total_shortage_qty` | 0.0264 | 缺料特征 |
| 7 | `expected_production_days` | 0.0242 | 基础特征 |
| 8 | `material_complexity` | 0.0231 | 物料特征 |
| 9 | `planned_start_quarter` | 0.0231 | 时间特征 |
| 10 | `planned_finish_weekday` | 0.0221 | 时间特征 |
| 11 | `shortage_qty_interaction` | 0.0204 | 交互特征 |
| 12 | `planned_start_weekday` | 0.0204 | 时间特征 |
| 13 | `material_target_encoded` | 0.0198 | 目标编码 |
| 14 | `qty_per_planned_day` | 0.0194 | 交互特征 |
| 15 | `line_avg_production_time_90d` | 0.0182 | 历史特征 |

**关键发现：**
✅ **最早开工天数和单位生产时长**是最强信号（占比共30%）  
✅ **创建到开始间隔**捕捉订单紧迫程度  
✅ **缺料比例特征**（shortage_qty_ratio）跃升前4，说明缺料严重程度对生产周期有重要影响  
✅ **5个缺料特征**全部进入Top 15  

---

## 📊 模型性能（v2，2026-04-15）

### 训练配置
- **算法**：XGBoost Regressor（reg:squarederror）
- **数据分割**：时序分割（chronological），前80%训练，后20%测试
- **验证方式**：5折时序交叉验证（TimeSeriesCV）
- **离群值过滤**：生产天数≤30天，订单数量≤500件

### 性能指标

| 数据集 | RMSE | MAE | R² |
|--------|------|-----|----|
| **训练集** | 1.155 天 | 0.819 天 | 0.748 |
| **测试集** | **1.751 天** | **1.113 天** | **0.313** |
| **CV均值（5折）** | **1.701 ± 0.218 天** | **1.141 ± 0.110 天** | **0.374 ± 0.136** |

### 各折详情

| Fold | RMSE | MAE | R² | 训练量 |
|------|------|-----|----|--------|
| Fold 1 | 1.827 | 1.336 | 0.214 | 417 |
| Fold 2 | 1.610 | 1.154 | 0.357 | 831 |
| Fold 3 | 1.316 | 0.997 | 0.627 | 1,245 |
| Fold 4 | 1.929 | 1.105 | 0.341 | 1,659 |
| Fold 5 | 1.819 | 1.115 | 0.331 | 2,073 |

> R² 在时序CV中随训练集增大趋于稳定（Fold 4-5 约 0.33-0.34）

### 历史版本对比

| 版本 | 模型类型 | Test RMSE | Test R² | CV R² | 特征数 |
|------|---------|-----------|---------|-------|--------|
| v1（旧） | 分类（XGB） | N/A | N/A（AUC=0.902） | N/A | 36 |
| v2-基础 | 回归（XGB），无缺料 | 1.759 | 0.291 | 0.358 | 47 |
| v2-缺料v1 | 回归+缺料绝对量 | 1.778 | 0.292 | 0.364 | 51 |
| **v2-缺料v2（当前）** | **回归+缺料比例** | **1.751** | **0.313** | **0.374** | **54** |

---

## 🔄 数据流程图（v2）

```
History.csv (2,491条)
    → 时序过滤（actual_finish_date存在）
    → 离群值过滤（days≤30, qty≤500）→ 2,487条

FG.csv → 物料复杂度、约束、生产时长
Capacity.csv → 产能信息
Shortage.csv (300,872条组件) → 聚合为订单级缺料特征

特征工程(v2):
    基础特征(8) + 时间特征(11) + 物料特征(5)
    + 并发负载(4) + 历史生产时长(7)[因果扩展均值]
    + 目标编码(1) + 缺料特征(7) + 产能特征(3) + 交互特征(8)
    = 54 维特征向量

时序分割:
    训练集: 前 1,989 条（时间最早的80%）
    测试集: 后   498 条（时间最晚的20%）

XGBoost Regressor → 预测 actual_production_days
    → Test RMSE: 1.751天, R²: 0.313
    → CV R²: 0.374 ± 0.136
```

---

## 💡 使用示例

### 训练：

```python
# 运行训练脚本（包含缺料数据）
python scripts/train_production_time_model.py
```

### 预测时输入：

```python
# X = 54维特征向量（预测时所有特征均可在订单开始前获得）
X_new = feature_engineer.transform(new_orders_df)

# 预测实际生产天数
predicted_days = model.predict(X_new)
# 输出: array([2.3, 4.7, 1.8, ...])

# 延迟风险判断
predicted_finish = actual_start_date + timedelta(days=predicted_days)
is_at_risk = predicted_finish > planned_finish_date
```

---

## 📝 数据要求总结

### ✅ 训练必需数据

**History.csv 必须包含：**
- `Actual finish date`（训练时计算标签用）
- `Actual start time`（训练时计算标签用）
- `Basic start date`（计划开始）
- `Basic finish date`（计划完成）
- `Order quantity`、`Material Number`、`Order`（生产订单号）

**FG.csv 必须包含：**`Material`, `Total production Time`, `Constraint`, `Production Line`

**Capacity.csv 必须包含：**`Production Line`, `Capacity`

**Shortage.csv（SAP MD04/MB52导出，可选但推荐）：**
- 列格式：`Order`, `Material`, `Description`, `Reqmnt qty`, `Available qty`, `Shortage qty`, `ReqmtsDate`
- 缺料量为正值或负值均支持（代码自动取绝对值）

### ✅ 预测时需要的数据

预测新订单时**不需要** `Actual finish date`，只需要：
- 订单基本信息（物料号、数量、计划日期）
- FG/Capacity主数据
- Shortage.csv（该订单当前缺料状态）

---

## 🎯 总结

| 项目 | v1（旧） | v2（当前） |
|------|---------|-----------|
| **预测目标** | `is_delayed`（0/1分类） | `actual_production_days`（回归） |
| **特征数量** | 36个 | 54个 |
| **数据源** | 5个CSV | 6个CSV（+Shortage） |
| **历史特征** | 全局均值填充（有泄露） | 因果扩展均值（无泄露） |
| **数据分割** | 随机分割（有泄露） | 时序分割（无泄露） |
| **验证方式** | 单次分割 | 5折TimeSeriesCV |
| **Test性能** | AUC=0.902（含泄露，虚高） | RMSE=1.751天，R²=0.313 |
