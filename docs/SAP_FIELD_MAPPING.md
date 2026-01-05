# SAP 字段映射表

## 📋 生产订单历史数据 (History.csv)

### 完整字段映射

| # | 目标字段 (CSV) | SAP OData 字段 | SAP 表.字段 | 数据类型 | 是否必需 | 转换规则 | 示例值 |
|---|---------------|---------------|------------|---------|---------|---------|--------|
| 1 | Sales Order | SalesOrder | AFKO.KDAUF | CHAR(10) | 是 | 去除前导零 | 504029252 |
| 2 | Sales Order Item | SalesOrderItem | AFKO.KDPOS | CHAR(6) | 是 | 保持原样 | 1001 |
| 3 | Order | OrderNumber | AUFK.AUFNR | CHAR(12) | 是 | 去除前导零 | 1351101544 |
| 4 | Material Number | MaterialNumber | AFKO.MATNR | CHAR(18) | 是 | 去除前导零 | CDX6090704R5012 |
| 5 | Material description | MaterialDescription | MAKT.MAKTX | CHAR(40) | 是 | UTF-8 编码 | VSC 7,2kV-400A 220V |
| 6 | System Status | SystemStatus | JEST.STAT | CHAR(40) | 否 | 拼接所有状态 | CLSD MSPT PRT CNF |
| 7 | Order quantity (GMEIN) | OrderQuantity | AFKO.GAMNG | DEC(13,3) | 是 | 转为浮点数 | 1.0 |
| 8 | Confirmed quantity (GMEIN) | ConfirmedQuantity | AFKO.WEMNG | DEC(13,3) | 否 | 转为浮点数 | 1.0 |
| 9 | Basic start date | BasicStartDate | AFKO.GSTRP | DATS(8) | 是 | YYYY-MM-DD | 2024-01-02 |
| 10 | Basic finish date | BasicFinishDate | AFKO.GLTRP | DATS(8) | 是 | YYYY-MM-DD | 2024-01-04 |
| 11 | Actual finish date | ActualFinishDate | AFKO.GETRI | DATS(8) | **是** | YYYY-MM-DD | 2024-01-03 |
| 12 | Unit of measure (=GMEIN) | UnitOfMeasure | AFKO.GMEIN | UNIT(3) | 否 | 保持原样 | PC |
| 13 | Created on | CreatedOn | AUFK.ERDAT | DATS(8) | 否 | YYYY-MM-DD | 2023-12-30 |
| 14 | Entered by | EnteredBy | AUFK.ERNAM | CHAR(12) | 否 | 保持原样 | CNSIGAN |
| 15 | Prodn Supervisor | ProductionSupervisor | AFKO.FEVOR | CHAR(6) | 否 | 保持原样 | VSC |
| 16 | MRP controller | MRPController | MARC.DISPO | CHAR(3) | 否 | 保持原样 | VSC |

### 关键过滤条件

```sql
-- 只要已完成的订单（有实际完成日期）
ActualFinishDate IS NOT NULL

-- 只要已关闭的订单
SystemStatus LIKE '%CLSD%'

-- 日期范围（建议最近2年）
BasicStartDate >= '20240101'
```

---

## 📦 物料主数据 (FG.csv)

### 字段映射

| # | 目标字段 | SAP OData 字段 | SAP 表.字段 | 数据类型 | 说明 |
|---|---------|---------------|------------|---------|------|
| 1 | Production Line | ProductionLine | CRHD.ARBPL | CHAR(8) | 工作中心/生产线 |
| 2 | Material | MaterialNumber | MARA.MATNR | CHAR(18) | 物料号（去前导零） |
| 3 | Material Description | MaterialDescription | MAKT.MAKTX | CHAR(40) | 物料描述 |
| 4 | Constraint | ConstraintFactor | **自定义字段** | INT | 最大日产能（件/天） |
| 5 | earlist strart date | EarliestStartDays | **自定义字段** | INT | 最早开始天数 |
| 6 | Total production Time | TotalProductionTime | **自定义字段** | DEC(5,2) | 单件生产时间（天） |

### ⚠️ 自定义字段说明

以下字段可能需要在 SAP 中创建自定义表或扩展标准表：

1. **ConstraintFactor** (最大日产能)
   - 建议位置: Z表 或 MARA 扩展字段
   - 数据来源: 工艺路线或产能规划数据
   - 示例值: 30 (表示该产线最多每天生产30件该物料)

2. **EarliestStartDays** (最早开始天数)
   - 建议位置: Z表 或物料主数据扩展
   - 数据来源: 采购提前期或生产准备时间
   - 示例值: 5 (表示需要提前5天准备)

3. **TotalProductionTime** (单件生产时间)
   - 建议位置: 工艺路线 (PLPO表) 或 Z表
   - 数据来源: 标准工时或工艺路线
   - 示例值: 2.5 (表示生产一件需要2.5天)

**如果这些字段不存在**，SAP 团队需要：
- 创建自定义表 (如 ZTABLE_FG_DATA)
- 或扩展标准表 (通过 Append Structure)
- 或从工艺路线计算得出

---

## 🏭 产线产能数据 (Capacity.csv)

### 字段映射

| # | 目标字段 | SAP OData 字段 | SAP 表.字段 | 数据类型 | 说明 |
|---|---------|---------------|------------|---------|------|
| 1 | Production Line | ProductionLine | CRHD.ARBPL | CHAR(8) | 工作中心 |
| 2 | Capacity | LineCapacity | CRHD.KAPAZ | DEC(8,2) | 标准产能 |

### 数据来源

- **CRHD**: 工作中心头数据
- **KAPID**: 产能头数据
- **KAKO**: 产能分类

---

## 🔄 数据转换规则详解

### 1. 日期转换

**SAP OData 日期格式**:
```json
"/Date(1704153600000)/"
```

**转换后**:
```
2024-01-02
```

**转换代码**:
```python
import re
from datetime import datetime

def convert_sap_date(sap_date):
    match = re.search(r'/Date\((\d+)\)/', sap_date)
    if match:
        timestamp = int(match.group(1)) / 1000
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    return None
```

### 2. 去除前导零

**SAP 格式**:
```
000000000CDX6090704R5012  (18位，前导零填充)
```

**转换后**:
```
CDX6090704R5012
```

**转换代码**:
```python
def remove_leading_zeros(value):
    return value.lstrip('0') or '0'
```

### 3. 数量转换

**SAP 格式**:
```
"1.000" (字符串)
```

**转换后**:
```
1.0 (浮点数)
```

### 4. 状态拼接

**SAP 格式** (JEST 表多行):
```
CLSD
MSPT
PRT
CNF
```

**转换后**:
```
CLSD MSPT PRT CNF
```

---

## 📊 数据量估算

### 预期数据量

| 数据类型 | 记录数 | 更新频率 | 说明 |
|---------|-------|---------|------|
| 生产订单历史 | ~2,500/年 | 每日增量 | 只要已完成的订单 |
| 物料主数据 | ~100 | 每周全量 | 相对稳定 |
| 产线产能 | ~5 | 每月全量 | 很少变化 |

### API 调用估算

**全量同步** (首次):
- 生产订单: 2,500 条 ÷ 1,000/批 = 3 次请求
- 物料数据: 1 次请求
- 产能数据: 1 次请求
- **总计**: ~5 次 API 调用

**增量同步** (每日):
- 生产订单: ~10 条/天 = 1 次请求
- 物料数据: 1 次请求（可选）
- 产能数据: 1 次请求（可选）
- **总计**: 1-3 次 API 调用

---

## 🎯 SAP 开发团队 Checklist

### Phase 1: 需求确认 ✅

- [ ] 确认 SAP 系统版本 (ECC / S/4HANA)
- [ ] 确认是否支持 OData v2/v4
- [ ] 确认 Gateway 是否已激活
- [ ] 确认自定义字段是否存在

### Phase 2: 开发准备 🔧

- [ ] 创建技术用户 (建议: ML_USER)
- [ ] 分配必要权限 (S_SERVICE, S_RFC, S_TABU_DIS)
- [ ] 准备开发环境 (SE80 / ADT)

### Phase 3: CDS View 开发 📝

- [ ] 创建 Z_PROD_ORDER_HISTORY CDS View
- [ ] 创建 Z_MATERIAL_MASTER CDS View
- [ ] 创建 Z_LINE_CAPACITY CDS View
- [ ] 激活 CDS Views

### Phase 4: OData 服务发布 🌐

- [ ] 在 SEGW 中创建 OData 服务
- [ ] 注册服务到 /IWFND/MAINT_SERVICE
- [ ] 测试服务 (浏览器访问 $metadata)
- [ ] 提供服务 URL 给 Python 团队

### Phase 5: 联调测试 🧪

- [ ] 提供测试环境访问
- [ ] 提供测试数据（至少100条订单）
- [ ] 配合 Python 团队进行接口测试
- [ ] 验证数据一致性

### Phase 6: 生产部署 🚀

- [ ] 在生产环境创建服务
- [ ] 配置生产用户和权限
- [ ] 性能测试和优化
- [ ] 文档交接

---

## 📞 联系信息

**Python 开发团队**:
- 负责人: [你的名字]
- 邮箱: [你的邮箱]
- 电话: [你的电话]

**SAP 开发团队**:
- 负责人: [待填写]
- 邮箱: [待填写]
- 电话: [待填写]

---

## 📅 时间计划

| 阶段 | 任务 | 负责方 | 预计工期 | 状态 |
|------|------|--------|---------|------|
| Week 1 | 需求确认、技术评审 | 双方 | 2天 | ⏳ 待开始 |
| Week 2 | CDS View 开发 | SAP 团队 | 3天 | ⏳ 待开始 |
| Week 2 | Python 客户端开发 | Python 团队 | 3天 | ✅ 已完成 |
| Week 3 | OData 服务发布 | SAP 团队 | 2天 | ⏳ 待开始 |
| Week 3 | 联调测试 | 双方 | 3天 | ⏳ 待开始 |
| Week 4 | 生产部署 | 双方 | 2天 | ⏳ 待开始 |
| Week 4 | 文档交接、培训 | 双方 | 1天 | ⏳ 待开始 |

---

需要更详细的技术规格说明吗？
