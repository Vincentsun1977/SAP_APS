# 🧪 SAP 连通性测试指南

## 🎯 目的

快速测试与 SAP 系统的连接，验证接口是否可用，并保存测试数据作为连通性证明。

---

## ⚡ 快速测试（3 步）

### 步骤 1: 确认配置

检查 `.env` 文件中的 SAP 连接信息：

```bash
# 查看当前配置
cat .env | grep SAP_
```

应该看到：
```env
SAP_HOST=cn-s-sapd061.cn.abb.com
SAP_PORT=44300
SAP_PROTOCOL=https
SAP_CLIENT=230
SAP_USERNAME=CNZHZHA62
SAP_PASSWORD=aBBaBB@DDD000666aBBaBB@DDD000666
SAP_ODATA_SERVICE=/sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV
```

⚠️ **注意**: `SAP_ODATA_SERVICE` 路径需要 SAP 团队提供实际值

---

### 步骤 2: 安装依赖（如果还没安装）

```bash
pip install requests python-dotenv pandas openpyxl
```

---

### 步骤 3: 运行测试

```bash
python scripts/simple_sap_test.py
```

---

## 📊 预期输出

### 成功的情况

```
🚀 开始 SAP 连通性测试...

✓ 找到配置文件: .env

================================================================================
🧪 SAP 连通性测试
================================================================================

步骤 1: 读取配置
--------------------------------------------------------------------------------
✓ SAP 主机: cn-s-sapd061.cn.abb.com:44300
✓ 客户端: 230
✓ 用户: CNZHZHA62
✓ 服务路径: /sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV

步骤 2: 构建请求
--------------------------------------------------------------------------------
✓ 请求 URL: https://cn-s-sapd061.cn.abb.com:44300/sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV/ProductionOrderSet
✓ 查询参数: top=10, filter=ActualFinishDate ne null

步骤 3: 发送请求到 SAP
--------------------------------------------------------------------------------
正在连接 cn-s-sapd061.cn.abb.com...
✓ HTTP 状态码: 200
✅ 请求成功

步骤 4: 解析响应数据
--------------------------------------------------------------------------------
✓ 原始响应已保存: data/sap_test/sap_response_20260105_143000.json
✓ 成功解析 10 条订单

步骤 5: 显示示例数据
--------------------------------------------------------------------------------

第一条订单数据:
  OrderNumber              : 1351101544
  SalesOrder               : 504029252
  SalesOrderItem           : 1001
  MaterialNumber           : CDX6090704R5012
  MaterialDescription      : VSC 7,2kV-400A 220V DCO Fixed Ver.
  SystemStatus             : CLSD MSPT PRT CNF DLV PRC CSER AZAE*
  OrderQuantity            : 1.000
  BasicStartDate           : /Date(1704153600000)/
  BasicFinishDate          : /Date(1704326400000)/
  ActualFinishDate         : /Date(1704240000000)/
  ...

步骤 6: 转换并保存数据
--------------------------------------------------------------------------------
✓ 数据已保存为 CSV: data/sap_test/sap_test_data_20260105_143000.csv
  - 行数: 10
  - 列数: 16
  - 列名: OrderNumber, SalesOrder, SalesOrderItem, MaterialNumber, MaterialDescription...
✓ 数据已保存为 Excel: data/sap_test/sap_test_data_20260105_143000.xlsx

步骤 7: 生成测试报告
--------------------------------------------------------------------------------
✓ 测试报告已保存: data/sap_test/connection_test_report_20260105_143000.txt

================================================================================
✅ SAP 连通性测试成功！
================================================================================

📊 测试结果:
  - 成功连接到 SAP 服务器
  - 成功获取 10 条生产订单数据
  - 数据已保存到: data/sap_test

📁 生成的文件:
  1. sap_response_20260105_143000.json - 原始 JSON 响应
  2. sap_test_data_20260105_143000.csv - CSV 格式数据
  3. sap_test_data_20260105_143000.xlsx - Excel 格式数据
  4. connection_test_report_20260105_143000.txt - 测试报告

💡 下一步:
  1. 查看测试数据: data/sap_test/sap_test_data_20260105_143000.csv
  2. 验证字段是否完整
  3. 联系 SAP 团队确认数据正确性
  4. 如果一切正常，可以运行完整同步:
     python scripts/sync_sap_data.py --test
================================================================================
```

---

## 🐛 常见错误及解决

### 错误 1: 配置不完整

```
❌ 配置不完整，请检查 .env 文件

必需的环境变量:
  - SAP_HOST
  - SAP_USERNAME
  - SAP_PASSWORD
  - SAP_ODATA_SERVICE (可选，有默认值)
```

**解决**:
```bash
# 编辑 .env 文件
nano .env

# 确保包含所有必需字段
SAP_HOST=your-sap-server.com
SAP_USERNAME=your_username
SAP_PASSWORD=your_password
SAP_ODATA_SERVICE=/sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV
```

---

### 错误 2: 认证失败 (401)

```
❌ 认证失败 (401)
   请检查用户名和密码是否正确
```

**解决**:
1. 确认用户名密码正确
2. 确认用户在 SAP 中未被锁定
3. 尝试在浏览器登录 SAP 验证密码
4. 联系 SAP 团队重置密码

---

### 错误 3: 服务不存在 (404)

```
❌ 服务不存在 (404)
   请确认 OData 服务已发布
   可以在浏览器访问: https://sap-server/sap/opu/odata/sap/Z_PROD_ORDER_HISTORY_SRV/$metadata
```

**解决**:
1. 联系 SAP 团队确认服务是否已创建
2. 在浏览器访问 `$metadata` URL 验证
3. 检查 `.env` 中的 `SAP_ODATA_SERVICE` 路径是否正确

---

### 错误 4: 连接超时

```
❌ 连接超时（>30秒）
   请检查网络连接和防火墙设置
```

**解决**:
```bash
# 测试网络连通性
ping cn-s-sapd061.cn.abb.com

# 测试端口（Windows）
Test-NetConnection -ComputerName cn-s-sapd061.cn.abb.com -Port 44300

# 测试端口（Linux）
telnet cn-s-sapd061.cn.abb.com 44300
```

---

### 错误 5: 未获取到数据

```
⚠️  未获取到订单数据
   可能原因:
   1. 过滤条件太严格（没有符合条件的数据）
   2. SAP 服务返回空结果
```

**解决**:
1. 联系 SAP 团队确认是否有测试数据
2. 检查过滤条件 `ActualFinishDate ne null`
3. 尝试去掉过滤条件获取所有数据

---

## 📁 测试输出文件

测试成功后，会在 `data/sap_test/` 目录生成以下文件：

### 1. JSON 原始响应
**文件**: `sap_response_YYYYMMDD_HHMMSS.json`

包含 SAP 返回的原始 JSON 数据，用于调试和验证。

### 2. CSV 数据文件
**文件**: `sap_test_data_YYYYMMDD_HHMMSS.csv`

转换后的 CSV 格式数据，可以用 Excel 或文本编辑器打开。

### 3. Excel 数据文件
**文件**: `sap_test_data_YYYYMMDD_HHMMSS.xlsx`

Excel 格式，更易于查看和分析。

### 4. 测试报告
**文件**: `connection_test_report_YYYYMMDD_HHMMSS.txt`

包含完整的测试信息和配置详情。

---

## ✅ 验证清单

测试成功后，请验证以下内容：

- [ ] 所有 4 个文件都已生成
- [ ] CSV/Excel 文件包含 10 条订单数据
- [ ] 订单数据包含以下关键字段：
  - [ ] OrderNumber (生产订单号)
  - [ ] MaterialNumber (物料号)
  - [ ] BasicStartDate (计划开始日期)
  - [ ] BasicFinishDate (计划完成日期)
  - [ ] ActualFinishDate (实际完成日期)
- [ ] 日期格式正确（SAP 格式：/Date(timestamp)/）
- [ ] 数据内容与 SAP 系统一致

---

## 📧 提交测试证明

测试成功后，可以将以下文件发送给相关方作为连通性证明：

1. **测试报告**: `connection_test_report_*.txt`
2. **Excel 数据**: `sap_test_data_*.xlsx`（可选，用于数据验证）

---

## 🎯 成功标准

✅ **连通性测试通过的标志**:
- HTTP 状态码 200
- 成功获取至少 1 条订单数据
- 数据包含所有必需字段
- 文件成功保存到 `data/sap_test/`

达到以上标准即可证明：
- ✅ 网络连接正常
- ✅ SAP 认证成功
- ✅ OData 服务可用
- ✅ 数据格式正确

---

## 🚀 测试成功后的下一步

1. **验证数据质量**
   - 打开 Excel 文件检查数据
   - 对比 SAP 系统中的原始数据

2. **运行完整测试**
   ```bash
   python scripts/test_sap_connection.py
   ```

3. **执行小批量同步测试**
   ```bash
   python scripts/sync_sap_data.py --test
   ```

4. **配置定时任务**（每日自动同步）

---

准备好运行测试了吗？只需一条命令：

```bash
python scripts/simple_sap_test.py
```
