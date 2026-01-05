# 🚀 SAP 集成快速开始指南

## 📋 前提条件

### Python 端（我们）
- ✅ Python 3.9+
- ✅ 已安装依赖: `pip install -r requirements.txt`
- ✅ SAP 集成代码已完成

### SAP 端（SAP 团队）
- ⏳ SAP S/4HANA 或 ECC 6.0+
- ⏳ Gateway 已激活
- ⏳ OData 服务已创建
- ⏳ 技术用户已创建并授权

---

## 🔧 配置步骤

### 步骤 1: 复制配置文件

```bash
# 复制配置模板
cp config/sap_config.yaml config/sap_config_prod.yaml
cp .env.example .env
```

### 步骤 2: 编辑 .env 文件

```bash
# 编辑 .env
nano .env
```

填入 SAP 连接信息:
```env
SAP_HOST=your-sap-server.com
SAP_PORT=443
SAP_PROTOCOL=https
SAP_CLIENT=100
SAP_USERNAME=ML_USER
SAP_PASSWORD=YourPassword123
```

### 步骤 3: 编辑 sap_config_prod.yaml

```bash
nano config/sap_config_prod.yaml
```

更新服务路径（由 SAP 团队提供）:
```yaml
sap:
  services:
    production_orders: "/sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV"
    material_master: "/sap/opu/odata/sap/Z_MATERIAL_MASTER_SRV"
    line_capacity: "/sap/opu/odata/sap/Z_LINE_CAPACITY_SRV"
```

---

## 🧪 测试连接

### 步骤 1: 运行连接测试

```bash
python scripts/test_sap_connection.py --config config/sap_config_prod.yaml
```

**预期输出**:
```
🧪 SAP 集成测试工具
======================================================================

测试 1: SAP 连接测试
======================================================================
✅ 连接成功

测试 2: 获取生产订单（前 10 条）
======================================================================
✅ 成功获取 10 条订单

示例订单:
  订单号: 1351101544
  物料号: CDX6090704R5012
  计划开始: 2024-01-02
  实际完成: 2024-01-03

...

📊 测试结果汇总
======================================================================
  连接测试              ✅ 通过
  获取订单              ✅ 通过
  获取物料              ✅ 通过
  数据转换              ✅ 通过
  获取元数据            ✅ 通过

总计: 5/5 测试通过
======================================================================

🎉 所有测试通过！可以开始数据同步。
```

### 如果测试失败

#### 错误 1: 连接超时
```
❌ 连接失败: 连接超时（>30秒）
```

**解决方案**:
- 检查网络连接
- 检查防火墙规则
- 确认 SAP 服务器地址和端口

#### 错误 2: 认证失败 (401)
```
❌ 认证失败，请检查用户名密码
```

**解决方案**:
- 检查 .env 中的用户名密码
- 确认用户在 SAP 中已创建
- 确认用户未被锁定

#### 错误 3: 服务不存在 (404)
```
❌ OData 服务不存在
```

**解决方案**:
- 联系 SAP 团队确认服务是否已发布
- 检查服务路径是否正确
- 在浏览器访问 `https://sap-server/sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV/$metadata`

---

## 📥 数据同步

### 首次全量同步

```bash
# 同步 2024 年至今的所有数据
python scripts/sync_sap_data.py \
  --mode full \
  --start-date 2024-01-01 \
  --config config/sap_config_prod.yaml
```

**预期输出**:
```
======================================================================
SAP 数据同步工具
======================================================================
加载配置: config/sap_config_prod.yaml
✓ 配置加载成功
测试 SAP 连接...
✓ SAP 连接测试成功

步骤 1/3: 提取生产订单历史
获取生产订单: start=2024-01-01, top=1000, skip=0
✓ 成功获取 1000 条订单
已获取 1000 条订单...
✓ 成功获取 1000 条订单
已获取 2000 条订单...
✓ 成功获取 491 条订单
✓ 总共获取 2491 条订单

步骤 2/3: 提取物料主数据
✓ 成功获取 77 条物料数据

步骤 3/3: 提取产线产能
✓ 成功获取 1 条产能数据

======================================================================
✓ 数据提取完成
  - 生产订单: 2491 条
  - 物料数据: 77 条
  - 产能数据: 1 条
======================================================================

保存数据到 CSV 文件
✓ 保存 History.csv: 2491 行
✓ 保存 FG.csv: 77 行
✓ 保存 Capacity.csv: 1 行

======================================================================
📊 同步完成摘要
======================================================================
模式: full
时间: 2026-01-05 14:30:00

数据统计:
  - 生产订单 (History.csv): 2491 条
  - 物料数据 (FG.csv): 77 条
  - 产能数据 (Capacity.csv): 1 条

文件位置: data/raw
======================================================================

💡 下一步操作:
  1. 检查数据文件: data/raw/History.csv
  2. 重新训练模型: python scripts/train_aps_model_optimized.py
  3. 运行预测: python scripts/predict_new_orders.py
```

### 每日增量同步

```bash
# 只同步新增/更新的数据
python scripts/sync_sap_data.py --mode incremental
```

### 测试模式（只提取少量数据）

```bash
# 测试模式：只提取最近 7 天数据
python scripts/sync_sap_data.py --test
```

---

## ⏰ 设置定时任务

### Linux (Cron)

```bash
# 编辑 crontab
crontab -e

# 添加每日凌晨 2 点同步任务
0 2 * * * cd /opt/sap-predictor && /opt/sap-predictor/venv/bin/python scripts/sync_sap_data.py --mode incremental >> logs/cron.log 2>&1
```

### Windows (任务计划程序)

```powershell
# 创建定时任务
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument "scripts\sync_sap_data.py --mode incremental" `
  -WorkingDirectory "C:\sap-production-delay-predictor"

$trigger = New-ScheduledTaskTrigger -Daily -At 2am

$principal = New-ScheduledTaskPrincipal `
  -UserId "SYSTEM" `
  -LogonType ServiceAccount `
  -RunLevel Highest

Register-ScheduledTask `
  -TaskName "SAP Data Sync" `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Description "每日同步 SAP 生产订单数据"
```

---

## 🔍 验证数据

### 检查同步的数据

```bash
# 查看文件
ls -lh data/raw/

# 查看行数
wc -l data/raw/History.csv
wc -l data/raw/FG.csv
wc -l data/raw/Capacity.csv

# 查看前几行
head -n 5 data/raw/History.csv
```

### 对比手动导出的数据

```python
# 对比脚本
import pandas as pd

# 手动导出的
df_manual = pd.read_csv('data/raw/History_manual.csv')

# API 提取的
df_api = pd.read_csv('data/raw/History.csv')

print(f"手动导出: {len(df_manual)} 行")
print(f"API 提取: {len(df_api)} 行")
print(f"差异: {abs(len(df_manual) - len(df_api))} 行")

# 检查字段
print(f"\n字段对比:")
print(f"手动: {list(df_manual.columns)}")
print(f"API:  {list(df_api.columns)}")
```

---

## 🔄 完整工作流

### 每日自动化流程

```bash
#!/bin/bash
# daily_update.sh - 每日自动更新脚本

set -e

echo "开始每日数据更新..."

# 1. 同步 SAP 数据
python scripts/sync_sap_data.py --mode incremental

# 2. 检查数据变化
NEW_ROWS=$(wc -l < data/raw/History.csv)
echo "当前数据行数: $NEW_ROWS"

# 3. 如果有新数据，重新训练模型
if [ $NEW_ROWS -gt 2500 ]; then
    echo "检测到新数据，开始重新训练模型..."
    python scripts/train_aps_model_optimized.py
fi

# 4. 发送通知
echo "每日更新完成: $(date)" | mail -s "SAP 数据同步完成" admin@company.com

echo "✓ 每日更新完成"
```

---

## 📊 监控与告警

### 检查同步状态

```bash
# 查看最后同步时间
cat .last_sap_sync

# 查看同步日志
tail -f logs/sap_sync_*.log

# 检查错误
grep "ERROR" logs/sap_sync_*.log
```

### 告警脚本

```python
# scripts/check_sync_health.py
from datetime import datetime, timedelta
from pathlib import Path

last_sync_file = Path('.last_sap_sync')

if last_sync_file.exists():
    with open(last_sync_file) as f:
        last_sync = datetime.fromisoformat(f.read().strip())
    
    hours_since = (datetime.now() - last_sync).total_seconds() / 3600
    
    if hours_since > 48:
        print(f"⚠️  警告: 已经 {hours_since:.1f} 小时未同步数据")
        # 发送告警邮件
    else:
        print(f"✅ 同步正常 (最后同步: {hours_since:.1f} 小时前)")
else:
    print("⚠️  从未同步过数据")
```

---

## 🐛 故障排查

### 常见问题

#### Q1: "ModuleNotFoundError: No module named 'src'"

**解决**:
```bash
# 确保在项目根目录运行
cd /path/to/sap-production-delay-predictor
python scripts/sync_sap_data.py
```

#### Q2: "配置验证失败"

**解决**:
```bash
# 检查环境变量
cat .env

# 检查配置文件
cat config/sap_config_prod.yaml

# 确保所有 ${VAR} 都有对应的环境变量
```

#### Q3: "SAP 连接超时"

**解决**:
```bash
# 测试网络连通性
ping sap-server.company.com

# 测试端口
telnet sap-server.company.com 443

# 增加超时时间（在 sap_config.yaml）
request:
  timeout: 60  # 增加到 60 秒
```

#### Q4: "数据为空"

**解决**:
- 检查日期范围是否正确
- 检查过滤条件是否太严格
- 联系 SAP 团队确认数据是否存在

---

## 📞 获取帮助

### 日志位置
- 同步日志: `logs/sap_sync_*.log`
- 错误日志: 同一文件中的 ERROR 级别

### 联系支持
- Python 团队: [你的邮箱]
- SAP 团队: [SAP 团队邮箱]

### 提交 Issue
https://github.com/Vincentsun1977/sap-production-delay-predictor/issues

---

## ✅ 验收标准

同步成功的标志:
- ✅ 测试脚本 5/5 通过
- ✅ History.csv 包含 > 2000 条记录
- ✅ FG.csv 包含 > 50 条物料
- ✅ Capacity.csv 包含 >= 1 条产线
- ✅ 所有必需字段无空值
- ✅ 日期格式正确 (YYYY-MM-DD)
- ✅ 数量字段为数值类型

---

准备好开始测试了吗？
