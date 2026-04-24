# 🔗 SAP 系统集成技术方案

## 📋 目录
- [概述](#概述)
- [技术方案对比](#技术方案对比)
- [推荐方案](#推荐方案)
- [接口设计](#接口设计)
- [数据映射](#数据映射)
- [实施步骤](#实施步骤)
- [安全与认证](#安全与认证)
- [错误处理](#错误处理)
- [性能优化](#性能优化)

---

## 📊 概述

### 目标
从 SAP 系统自动提取生产订单历史数据，用于机器学习模型训练，替代手动导出 CSV 文件的方式。

### 需求
1. **数据源**: SAP ERP/S4HANA 生产订单模块
2. **数据量**: 历史订单数据（建议最近2年）
3. **更新频率**: 每日/每周增量同步
4. **数据表**: 涉及 5 个主要数据源

---

## 🔄 技术方案对比

### 方案 1: SAP OData API ⭐ **推荐**

**优点**：
- ✅ RESTful 风格，易于集成
- ✅ 标准 HTTP/JSON，Python 支持好
- ✅ 支持过滤、分页、增量查询
- ✅ SAP S/4HANA 原生支持
- ✅ 无需额外中间件

**缺点**：
- ⚠️ 需要 SAP 开启 OData 服务
- ⚠️ 可能需要自定义 CDS View

**适用场景**: SAP S/4HANA 或 SAP NetWeaver Gateway

---

### 方案 2: SAP RFC (Remote Function Call)

**优点**：
- ✅ SAP 标准接口，功能强大
- ✅ 支持所有 SAP 版本（ECC/S4）
- ✅ 可调用 BAPI/Function Module
- ✅ 实时数据访问

**缺点**：
- ⚠️ 需要安装 SAP NetWeaver RFC SDK
- ⚠️ Python 库 pyrfc 配置复杂
- ⚠️ 需要 SAP 授权用户

**适用场景**: SAP ECC 6.0 或需要调用复杂业务逻辑

---

### 方案 3: SAP IDoc (Intermediate Document)

**优点**：
- ✅ 异步传输，不影响 SAP 性能
- ✅ 支持批量数据传输
- ✅ 有重试机制

**缺点**：
- ⚠️ 配置复杂，需要 SAP Basis 支持
- ⚠️ 实时性差
- ⚠️ 需要中间件（如 SAP PI/PO）

**适用场景**: 大批量历史数据迁移

---

### 方案 4: 数据库直连 (只读)

**优点**：
- ✅ 最快速度
- ✅ 灵活查询
- ✅ 无需 SAP 开发

**缺点**：
- ❌ 违反 SAP 许可协议（不推荐）
- ❌ 数据结构复杂（需要理解 SAP 表结构）
- ❌ 安全风险高

**适用场景**: 仅用于开发/测试环境

---

## ⭐ 推荐方案: SAP OData API

### 架构图

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   SAP S/4HANA   │         │  Python 应用层   │         │  ML 训练系统    │
│                 │         │                  │         │                 │
│  ┌───────────┐  │         │  ┌────────────┐  │         │  ┌───────────┐  │
│  │ CDS View  │  │◄────────┤  │ SAP Client │  │         │  │  XGBoost  │  │
│  │ (OData)   │  │  HTTP   │  │  Connector │  │         │  │   Model   │  │
│  └───────────┘  │         │  └────────────┘  │         │  └───────────┘  │
│                 │         │         │        │         │        ▲        │
│  ┌───────────┐  │         │  ┌──────▼──────┐ │         │  ┌─────┴─────┐  │
│  │ 生产订单   │  │         │  │ Data Trans- │ │────────►│  │  Training │  │
│  │   表       │  │         │  │   former    │ │  CSV    │  │   Data    │  │
│  └───────────┘  │         │  └─────────────┘ │         │  └───────────┘  │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

---

## 🔌 接口设计

### 1. SAP 端需要提供的 OData 服务

#### 服务 1: 生产订单历史数据 (ABB/Test/ZTTPP_APS/ProductionOrder)

**Entity Set**: `ProductionOrderSet`

**字段清单**:

| SAP 字段名 | 技术名称 | 数据类型 | 说明 | 对应 History.csv |
|-----------|---------|---------|------|-----------------|
| AUFNR | OrderNumber | String(12) | 生产订单号 | Order |
| VBELN | SalesOrder | String(10) | 销售订单号 | Sales Order |
| POSNR | SalesOrderItem | String(6) | 销售订单行项目 | Sales Order Item |
| MATNR | MaterialNumber | String(18) | 物料号 | Material Number |
| MAKTX | MaterialDescription | String(40) | 物料描述 | Material description |
| STAT | SystemStatus | String(40) | 系统状态 | System Status |
| GAMNG | OrderQuantity | Decimal | 订单数量 | Order quantity (GMEIN) |
| WEMNG | ConfirmedQuantity | Decimal | 确认数量 | Confirmed quantity (GMEIN) |
| GSTRP | BasicStartDate | Date | 基本开始日期 | Basic start date |
| GLTRP | BasicFinishDate | Date | 基本完成日期 | Basic finish date |
| GETRI | ActualFinishDate | Date | 实际完成日期 | Actual finish date |
| GMEIN | UnitOfMeasure | String(3) | 计量单位 | Unit of measure (=GMEIN) |
| ERDAT | CreatedOn | Date | 创建日期 | Created on |
| ERNAM | EnteredBy | String(12) | 创建人 | Entered by |
| FEVOR | ProductionSupervisor | String(6) | 生产主管 | Prodn Supervisor |
| DISPO | MRPController | String(3) | MRP控制员 | MRP controller |

**过滤条件**:
```
$filter=ActualFinishDate ne null and 
        BasicStartDate ge datetime'2024-01-01T00:00:00' and
        SystemStatus eq 'CLSD'
```

**示例 URL**:
```
https://sap-server:port/sap/opu/odata/sap/ABB/Test/ZTTPP_APS/ProductionOrder/ProductionOrderSet?
  $filter=ActualFinishDate ne null and BasicStartDate ge datetime'2024-01-01T00:00:00'
  &$format=json
  &$top=1000
  &$skip=0
```

---

#### 服务 2: 物料主数据 (Z_MATERIAL_MASTER_SRV)

**Entity Set**: `MaterialSet`

| SAP 字段 | 技术名称 | 说明 | 对应 FG.csv |
|---------|---------|------|------------|
| MATNR | MaterialNumber | 物料号 | Material |
| MAKTX | MaterialDescription | 物料描述 | Material Description |
| ARBPL | ProductionLine | 生产线 | Production Line |
| CONSTRAINT | ConstraintFactor | 最大日产能 | Constraint |
| EARLIEST_START | EarliestStartDays | 最早开始天数 | earlist strart date |
| PROD_TIME | TotalProductionTime | 单件生产时间(天) | Total production Time |

---

#### 服务 3: 产线产能数据 (Z_LINE_CAPACITY_SRV)

**Entity Set**: `CapacitySet`

| SAP 字段 | 技术名称 | 说明 | 对应 Capacity.csv |
|---------|---------|------|------------------|
| ARBPL | ProductionLine | 生产线 | Production Line |
| CAPACITY | LineCapacity | 标准日产能 | Capacity |

---

### 2. Python 端接口实现

#### 核心模块结构

```
src/
├── sap_integration/
│   ├── __init__.py
│   ├── sap_client.py           # SAP OData 客户端
│   ├── data_extractor.py       # 数据提取器
│   ├── data_transformer.py     # 数据转换器
│   ├── config.py               # 配置管理
│   └── exceptions.py           # 自定义异常
├── config/
│   └── sap_config.yaml         # SAP 连接配置
└── scripts/
    ├── sync_sap_data.py        # 数据同步脚本
    └── test_sap_connection.py  # 连接测试脚本
```

---

## 📝 接口规范文档

### API 端点定义

#### 1. 获取生产订单历史

**请求**:
```http
GET /sap/opu/odata/sap/ABB/Test/ZTTPP_APS/ProductionOrder/ProductionOrderSet
Authorization: Basic <base64_credentials>
Accept: application/json

Query Parameters:
  $filter: ActualFinishDate ne null and BasicStartDate ge datetime'2024-01-01T00:00:00'
  $format: json
  $top: 1000
  $skip: 0
  $orderby: BasicStartDate desc
```

**响应**:
```json
{
  "d": {
    "results": [
      {
        "OrderNumber": "1351101544",
        "SalesOrder": "504029252",
        "SalesOrderItem": "1001",
        "MaterialNumber": "CDX6090704R5012",
        "MaterialDescription": "VSC 7,2kV-400A 220V DCO Fixed Ver.",
        "SystemStatus": "CLSD MSPT PRT CNF DLV PRC CSER AZAE*",
        "OrderQuantity": "1.000",
        "ConfirmedQuantity": "1.000",
        "BasicStartDate": "/Date(1704153600000)/",
        "BasicFinishDate": "/Date(1704326400000)/",
        "ActualFinishDate": "/Date(1704240000000)/",
        "UnitOfMeasure": "PC",
        "CreatedOn": "/Date(1703894400000)/",
        "EnteredBy": "CNSIGAN",
        "ProductionSupervisor": "VSC",
        "MRPController": "VSC"
      }
    ]
  }
}
```

#### 2. 获取物料主数据

**请求**:
```http
GET /sap/opu/odata/sap/Z_MATERIAL_MASTER_SRV/MaterialSet
Authorization: Basic <base64_credentials>
Accept: application/json

Query Parameters:
  $format: json
  $select: MaterialNumber,MaterialDescription,ProductionLine,ConstraintFactor,EarliestStartDays,TotalProductionTime
```

**响应**:
```json
{
  "d": {
    "results": [
      {
        "MaterialNumber": "CDX6090704R5001",
        "MaterialDescription": "VSC/P 7,2kV-400A 220V SCO",
        "ProductionLine": "VSC",
        "ConstraintFactor": "30",
        "EarliestStartDays": "5",
        "TotalProductionTime": "2.5"
      }
    ]
  }
}
```

#### 3. 获取产线产能

**请求**:
```http
GET /sap/opu/odata/sap/Z_LINE_CAPACITY_SRV/CapacitySet
```

**响应**:
```json
{
  "d": {
    "results": [
      {
        "ProductionLine": "VSC",
        "LineCapacity": "15"
      }
    ]
  }
}
```

---

## 🗺️ 数据映射表

### History.csv 字段映射

| 目标字段 (CSV) | SAP OData 字段 | SAP 表.字段 | 数据类型 | 转换规则 |
|---------------|---------------|------------|---------|---------|
| Sales Order | SalesOrder | VBAK.VBELN | String | 去除前导零 |
| Sales Order Item | SalesOrderItem | VBAP.POSNR | String | 保持原样 |
| Order | OrderNumber | AUFK.AUFNR | String | 去除前导零 |
| Material Number | MaterialNumber | MARA.MATNR | String | 去除前导零 |
| Material description | MaterialDescription | MAKT.MAKTX | String | UTF-8 编码 |
| System Status | SystemStatus | JEST.STAT | String | 拼接所有状态 |
| Order quantity (GMEIN) | OrderQuantity | AFKO.GAMNG | Decimal | 转为浮点数 |
| Confirmed quantity (GMEIN) | ConfirmedQuantity | AFKO.WEMNG | Decimal | 转为浮点数 |
| Basic start date | BasicStartDate | AFKO.GSTRP | Date | 转为 YYYY-MM-DD |
| Basic finish date | BasicFinishDate | AFKO.GLTRP | Date | 转为 YYYY-MM-DD |
| Actual finish date | ActualFinishDate | AFKO.GETRI | Date | 转为 YYYY-MM-DD |
| Unit of measure (=GMEIN) | UnitOfMeasure | AFKO.GMEIN | String | 保持原样 |
| Created on | CreatedOn | AUFK.ERDAT | Date | 转为 YYYY-MM-DD |
| Entered by | EnteredBy | AUFK.ERNAM | String | 保持原样 |
| Prodn Supervisor | ProductionSupervisor | AFKO.FEVOR | String | 保持原样 |
| MRP controller | MRPController | MARC.DISPO | String | 保持原样 |

### FG.csv 字段映射

| 目标字段 | SAP 字段 | SAP 表.字段 | 说明 |
|---------|---------|-----------|------|
| Production Line | ProductionLine | CRHD.ARBPL | 工作中心 |
| Material | MaterialNumber | MARA.MATNR | 物料号 |
| Material Description | MaterialDescription | MAKT.MAKTX | 物料描述 |
| Constraint | ConstraintFactor | Z_CUSTOM.CONSTRAINT | 最大日产能（自定义字段） |
| earlist strart date | EarliestStartDays | Z_CUSTOM.EARLIEST_START | 最早开始天数 |
| Total production Time | TotalProductionTime | Z_CUSTOM.PROD_TIME | 单件生产时间(天) |

### Capacity.csv 字段映射

| 目标字段 | SAP 字段 | SAP 表.字段 | 说明 |
|---------|---------|-----------|------|
| Production Line | ProductionLine | CRHD.ARBPL | 工作中心 |
| Capacity | LineCapacity | CRHD.KAPAZ | 标准产能 |

---

## 🛠️ 实施步骤

### 阶段 1: SAP 端开发 (SAP 开发团队负责)

#### 步骤 1.1: 创建 CDS View (推荐)

**文件**: `Z_PROD_ORDER_HISTORY`

```abap
@AbapCatalog.sqlViewName: 'ZPRODORDHIST'
@AbapCatalog.compiler.compareFilter: true
@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'Production Order History for ML'
@OData.publish: true

define view Z_PROD_ORDER_HISTORY
  as select from aufk as OrderHeader
  
  association [0..1] to afko as _OrderData 
    on OrderHeader.aufnr = _OrderData.aufnr
    
  association [0..1] to vbap as _SalesOrderItem
    on _OrderData.kdauf = _SalesOrderItem.vbeln
    and _OrderData.kdpos = _SalesOrderItem.posnr
    
  association [0..1] to makt as _MaterialText
    on _OrderData.matnr = _MaterialText.matnr
    and _MaterialText.spras = 'E'
    
{
  key OrderHeader.aufnr as OrderNumber,
  
  _OrderData.kdauf as SalesOrder,
  _OrderData.kdpos as SalesOrderItem,
  _OrderData.matnr as MaterialNumber,
  _MaterialText.maktx as MaterialDescription,
  OrderHeader.astkz as SystemStatus,
  _OrderData.gamng as OrderQuantity,
  _OrderData.wemng as ConfirmedQuantity,
  _OrderData.gstrp as BasicStartDate,
  _OrderData.gltrp as BasicFinishDate,
  _OrderData.getri as ActualFinishDate,
  _OrderData.gmein as UnitOfMeasure,
  OrderHeader.erdat as CreatedOn,
  OrderHeader.ernam as EnteredBy,
  _OrderData.fevor as ProductionSupervisor,
  _OrderData.dispo as MRPController
}
where _OrderData.getri is not null  // 只要已完成的订单
```

#### 步骤 1.2: 创建物料主数据 CDS View

**文件**: `Z_MATERIAL_MASTER`

```abap
@AbapCatalog.sqlViewName: 'ZMATMASTER'
@OData.publish: true

define view Z_MATERIAL_MASTER
  as select from mara as Material
  
  association [0..1] to makt as _Text
    on Material.matnr = _Text.matnr
    and _Text.spras = 'E'
    
  association [0..1] to ztable_fg as _FGData
    on Material.matnr = _FGData.matnr
    
{
  key Material.matnr as MaterialNumber,
  _Text.maktx as MaterialDescription,
  _FGData.arbpl as ProductionLine,
  _FGData.constraint as ConstraintFactor,
  _FGData.earliest_start as EarliestStartDays,
  _FGData.prod_time as TotalProductionTime
}
```

#### 步骤 1.3: 激活 OData 服务

在 SAP Gateway (SEGW) 中：
1. 创建服务 `ABB/Test/ZTTPP_APS/ProductionOrder`
2. 注册服务到 `/IWFND/MAINT_SERVICE`
3. 分配权限给技术用户

---

### 阶段 2: Python 端开发 (我们负责)

#### 步骤 2.1: 安装依赖

```bash
pip install requests python-dotenv pyyaml pandas
```

#### 步骤 2.2: 配置文件

**文件**: `.env`

```env
# SAP 连接配置
SAP_HOST=sap-server.company.com
SAP_PORT=443
SAP_PROTOCOL=https
SAP_CLIENT=100
SAP_USERNAME=ML_USER
SAP_PASSWORD=your_password

# OData 服务路径
SAP_ODATA_HISTORY=/sap/opu/odata/sap/ABB/Test/ZTTPP_APS/ProductionOrder
SAP_ODATA_MATERIAL=/sap/opu/odata/sap/Z_MATERIAL_MASTER_SRV
SAP_ODATA_CAPACITY=/sap/opu/odata/sap/Z_LINE_CAPACITY_SRV

# 数据同步配置
SYNC_START_DATE=2024-01-01
SYNC_BATCH_SIZE=1000
SYNC_OUTPUT_DIR=data/raw
```

#### 步骤 2.3: SAP 客户端实现

见下方代码实现部分。

---

### 阶段 3: 联调测试

#### 测试清单

- [ ] **连接测试**: 验证网络连通性和认证
- [ ] **数据提取测试**: 提取少量数据验证字段映射
- [ ] **增量同步测试**: 验证增量更新逻辑
- [ ] **性能测试**: 测试大批量数据提取性能
- [ ] **错误处理测试**: 模拟网络中断、认证失败等场景
- [ ] **数据质量验证**: 对比手动导出和 API 提取的数据一致性

---

## 🔐 安全与认证

### 认证方式

#### 方式 1: Basic Authentication (开发/测试)

```python
import base64

credentials = f"{username}:{password}"
encoded = base64.b64encode(credentials.encode()).decode()
headers = {
    "Authorization": f"Basic {encoded}"
}
```

#### 方式 2: OAuth 2.0 (生产推荐)

```python
import requests

# 获取 token
token_url = "https://sap-server/sap/bc/sec/oauth2/token"
data = {
    "grant_type": "client_credentials",
    "client_id": "your_client_id",
    "client_secret": "your_client_secret"
}

response = requests.post(token_url, data=data)
access_token = response.json()["access_token"]

headers = {
    "Authorization": f"Bearer {access_token}"
}
```

#### 方式 3: X.509 证书认证 (最安全)

```python
import requests

response = requests.get(
    url,
    cert=('/path/to/client.crt', '/path/to/client.key'),
    verify='/path/to/ca.crt'
)
```

### 权限要求

SAP 端需要为技术用户分配以下权限：

| 权限对象 | 字段 | 值 | 说明 |
|---------|------|----|----|
| S_RFC | RFC_NAME | Z_PROD_* | 允许调用自定义 RFC |
| S_TABU_DIS | DICBERCLS | &NC& | 允许读取表数据 |
| S_SERVICE | SRV_NAME | ABB/Test/ZTTPP_APS/ProductionOrder | OData 服务权限 |

---

## ⚡ 性能优化

### 1. 分页查询

```python
def fetch_all_orders(client, start_date, batch_size=1000):
    """分页获取所有订单"""
    all_orders = []
    skip = 0
    
    while True:
        orders = client.get_orders(
            start_date=start_date,
            top=batch_size,
            skip=skip
        )
        
        if not orders:
            break
            
        all_orders.extend(orders)
        skip += batch_size
        
        print(f"已获取 {len(all_orders)} 条订单...")
    
    return all_orders
```

### 2. 增量同步

```python
def sync_incremental(client, last_sync_date):
    """增量同步（只获取新数据）"""
    filter_str = f"BasicStartDate ge datetime'{last_sync_date}T00:00:00'"
    
    new_orders = client.get_orders(filter=filter_str)
    
    # 保存最后同步时间
    with open('.last_sync', 'w') as f:
        f.write(datetime.now().isoformat())
    
    return new_orders
```

### 3. 并行请求

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_parallel(client, date_ranges):
    """并行获取多个日期范围的数据"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(client.get_orders, start_date=start, end_date=end)
            for start, end in date_ranges
        ]
        
        results = [f.result() for f in futures]
    
    return [order for batch in results for order in batch]
```

---

## 🚨 错误处理

### 常见错误及处理

| 错误类型 | HTTP 状态码 | 处理方式 |
|---------|-----------|---------|
| 认证失败 | 401 | 检查用户名密码，刷新 token |
| 权限不足 | 403 | 联系 SAP Basis 分配权限 |
| 服务不存在 | 404 | 检查 OData 服务是否激活 |
| 请求超时 | 408/504 | 减小批次大小，增加重试 |
| 服务器错误 | 500 | 记录日志，稍后重试 |
| 数据格式错误 | - | 数据验证，记录异常数据 |

### 重试策略

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def fetch_with_retry(url, headers):
    """带重试的请求"""
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
```

---

## 📅 数据同步策略

### 策略 1: 全量同步（初次）

```python
# 首次运行：获取所有历史数据
python scripts/sync_sap_data.py --mode full --start-date 2024-01-01
```

### 策略 2: 增量同步（日常）

```python
# 每日定时任务：只获取新增/更新的数据
python scripts/sync_sap_data.py --mode incremental
```

### 策略 3: 定时任务配置

**Linux Cron**:
```bash
# 每天凌晨 2 点同步数据
0 2 * * * cd /opt/sap-predictor && python scripts/sync_sap_data.py --mode incremental
```

**Windows 任务计划程序**:
```powershell
# 创建每日任务
$action = New-ScheduledTaskAction -Execute "python" -Argument "scripts/sync_sap_data.py --mode incremental" -WorkingDirectory "C:\sap-predictor"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "SAP Data Sync" -Action $action -Trigger $trigger
```

---

## 🔄 数据流程

```
┌──────────────────────────────────────────────────────────────┐
│                    完整数据同步流程                            │
└──────────────────────────────────────────────────────────────┘

1. 连接 SAP
   ├─ 读取配置 (.env)
   ├─ 建立连接 (HTTPS)
   └─ 认证 (Basic/OAuth)
   
2. 提取数据
   ├─ 调用 OData API
   ├─ 分页获取 (每批 1000 条)
   ├─ 解析 JSON 响应
   └─ 数据验证
   
3. 转换数据
   ├─ 字段映射
   ├─ 日期格式转换
   ├─ 去除前导零
   ├─ 编码转换 (UTF-8)
   └─ 数据清洗
   
4. 保存数据
   ├─ 保存为 CSV (data/raw/)
   ├─ 记录同步日志
   └─ 更新同步时间戳
   
5. 触发训练
   ├─ 检测数据变化
   ├─ 自动触发模型训练
   └─ 发送通知
```

---

## 📋 SAP 开发团队对接清单

### 需要 SAP 团队提供

#### 1. 技术信息
- [ ] SAP 系统版本 (ECC 6.0 / S/4HANA)
- [ ] Gateway 服务器地址和端口
- [ ] 客户端编号 (Client)
- [ ] 是否支持 OData v2/v4

#### 2. 访问权限
- [ ] 技术用户账号 (建议创建专用用户 `ML_USER`)
- [ ] 用户密码（或 OAuth Client ID/Secret）
- [ ] 分配必要的权限角色

#### 3. OData 服务
- [ ] 创建生产订单历史 OData 服务
- [ ] 创建物料主数据 OData 服务
- [ ] 创建产线产能 OData 服务
- [ ] 提供服务 URL 和 Metadata

#### 4. 自定义字段（如果不存在）
- [ ] `Constraint` (最大日产能) - 可能需要在物料主数据扩展
- [ ] `Earliest Start Days` (最早开始天数)
- [ ] `Total Production Time` (单件生产时间)

#### 5. 测试环境
- [ ] 提供测试系统访问
- [ ] 提供测试数据（至少 100 条订单）
- [ ] 提供 API 测试工具（如 Postman Collection）

---

## 📞 对接沟通模板

### 邮件模板（发给 SAP 开发团队）

```
主题: SAP 生产订单数据接口开发需求

尊敬的 SAP 开发团队，

我们正在开发一个基于机器学习的生产延迟预测系统，需要从 SAP 系统自动提取历史生产订单数据。

【需求概述】
- 目的: 自动化数据提取，替代手动导出 CSV
- 数据量: 约 2,500 条历史订单/年
- 更新频率: 每日增量同步
- 技术方案: SAP OData API (推荐)

【需要的数据】
1. 生产订单历史 (AUFK/AFKO 表)
   - 字段: 见附件《字段映射表.xlsx》
   - 过滤条件: 实际完成日期不为空，状态为已关闭

2. 物料主数据 (MARA/MAKT + 自定义字段)
   - 生产线、产能、生产时间等

3. 产线产能数据 (CRHD 表)

【技术方案建议】
方案 A (推荐): 创建 CDS View + OData 服务
  - 优点: 标准化、易维护、性能好
  - 工作量: 约 2-3 人天
  
方案 B (备选): RFC Function Module
  - 优点: 灵活、功能强大
  - 工作量: 约 3-5 人天

【需要你们提供】
1. SAP 系统技术信息（版本、Gateway 地址）
2. 技术用户账号和权限
3. OData 服务 URL 和 Metadata
4. 测试环境访问

【我们提供】
1. 详细的字段映射表
2. API 调用示例代码
3. 数据格式说明文档
4. 联调测试支持

【时间计划】
- Week 1: 需求确认、技术方案评审
- Week 2: SAP 端开发（CDS View + OData）
- Week 3: Python 端开发和联调测试
- Week 4: 生产环境部署和验证

期待与你们合作！

附件:
- SAP_INTEGRATION.md (技术方案详细文档)
- 字段映射表.xlsx
- API 调用示例.postman_collection.json

联系人: [你的名字]
邮箱: [你的邮箱]
```

---

## 🧪 测试方案

### 单元测试

```python
# tests/test_sap_client.py
import pytest
from src.sap_integration.sap_client import SAPODataClient

def test_connection():
    """测试 SAP 连接"""
    client = SAPODataClient()
    assert client.test_connection() == True

def test_fetch_orders():
    """测试订单提取"""
    client = SAPODataClient()
    orders = client.get_orders(top=10)
    assert len(orders) > 0
    assert 'OrderNumber' in orders[0]

def test_date_conversion():
    """测试日期转换"""
    sap_date = "/Date(1704153600000)/"
    converted = convert_sap_date(sap_date)
    assert converted == "2024-01-02"
```

### 集成测试

```bash
# 测试完整流程
python scripts/test_sap_integration.py --test-mode
```

---

## 📊 监控与日志

### 日志记录

```python
from loguru import logger

logger.add(
    "logs/sap_sync_{time}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)

# 记录关键操作
logger.info(f"开始同步 SAP 数据: {start_date} - {end_date}")
logger.info(f"成功获取 {len(orders)} 条订单")
logger.error(f"同步失败: {error_message}")
```

### 监控指标

- 同步成功率
- 数据量统计
- API 响应时间
- 错误次数和类型

---

## 🎯 备选方案

### 如果 OData 不可行

#### 方案 B: SAP RFC + pyrfc

```python
from pyrfc import Connection

conn = Connection(
    user='ML_USER',
    passwd='password',
    ashost='sap-server',
    sysnr='00',
    client='100'
)

# 调用 BAPI
result = conn.call('BAPI_PRODORD_GET_DETAIL', NUMBER='1351101544')
```

#### 方案 C: 定时 CSV 导出 + 文件监控

```python
# SAP 端: 配置后台作业，每日导出 CSV 到共享目录
# Python 端: 监控目录，自动导入新文件

import watchdog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CSVHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith('.csv'):
            process_csv(event.src_path)
```

---

## 📦 交付物清单

### 给 SAP 团队

1. ✅ `SAP_INTEGRATION.md` - 技术方案文档（本文件）
2. ✅ `SAP_FIELD_MAPPING.xlsx` - 字段映射表
3. ✅ `SAP_API_SPEC.yaml` - OpenAPI 规范
4. ✅ `CDS_VIEW_TEMPLATE.abap` - CDS View 模板代码
5. ✅ `POSTMAN_COLLECTION.json` - API 测试集合

### Python 实现代码

1. ✅ `src/sap_integration/sap_client.py` - SAP 客户端
2. ✅ `src/sap_integration/data_extractor.py` - 数据提取器
3. ✅ `src/sap_integration/data_transformer.py` - 数据转换器
4. ✅ `scripts/sync_sap_data.py` - 同步脚本
5. ✅ `scripts/test_sap_connection.py` - 测试脚本
6. ✅ `config/sap_config.yaml` - 配置文件模板

---

## 🎓 培训材料

### 给 SAP 团队的培训

1. **OData 基础** (30分钟)
   - OData 协议介绍
   - CDS View 开发
   - Gateway 服务激活

2. **接口开发实战** (1小时)
   - 创建 CDS View
   - 测试 OData 服务
   - 权限配置

3. **联调测试** (1小时)
   - Postman 测试
   - Python 客户端测试
   - 问题排查

---

## 📞 支持与维护

### 运维支持

- **监控**: 每日同步日志检查
- **告警**: 同步失败自动邮件通知
- **备份**: 保留最近 30 天的原始数据
- **文档**: 维护接口变更日志

### SLA 建议

- **可用性**: 99.5% (允许每月 3.6 小时维护窗口)
- **响应时间**: API 调用 < 5 秒
- **数据延迟**: 增量同步延迟 < 24 小时

---

需要我立即创建 Python 实现代码吗？
