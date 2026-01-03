# SAP生产延迟预测系统 - 部署说明

## 📋 系统要求

- **Python**: 3.9+
- **操作系统**: macOS / Linux / Windows
- **内存**: 最低 4GB RAM
- **磁盘**: 最低 2GB 可用空间

---

## 📦 依赖清单

### 核心依赖
```
pandas>=2.0.0
numpy>=1.24.0
xgboost>=2.0.0
scikit-learn>=1.3.0
loguru>=0.7.0
```

### Dashboard相关
```
streamlit>=1.28.0
plotly>=5.17.0
```

### 数据库（可选）
```
supabase>=2.0.0
```

### 完整依赖列表
参考项目根目录的 `requirements.txt` 文件

---

## 🚀 快速部署

### 1. 克隆/下载项目

```bash
# 如果使用Git
git clone <repository-url>
cd sap-production-predictor

# 或者直接解压项目文件夹
cd /path/to/sap-production-predictor
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

**注意事项：**
- macOS用户可能需要安装 `libomp`：
  ```bash
  brew install libomp
  ```
- 如果安装失败，尝试升级pip：
  ```bash
  pip install --upgrade pip
  ```

### 4. 准备数据

将以下CSV文件放入 `data/raw/` 目录：

```
data/raw/
├── Order.csv       # 订单数据
├── FG.csv          # 成品主数据
├── Capacity.csv    # 产能数据
├── APS.csv         # APS计划数据
└── History.csv     # 历史完成数据（必需）
```

**数据格式要求：**

- **History.csv** 必须包含字段：
  - Sales Order（销售订单号）
  - Order（生产订单号）
  - Material Number（物料号）
  - Basic start date（计划开始）
  - Basic finish date（计划完成）
  - **Actual finish date（实际完成）** ← 必需！

### 5. 训练模型

```bash
# 确保在项目根目录
python scripts/train_aps_model.py
```

**预期输出：**
```
✓ 加载了 2,491 条历史订单
✓ 训练数据: 2491 rows × 36 features
✓ 模型准确率: 91.2%
✓ 模型已保存: models/aps_xgb_model_YYYYMMDD_HHMMSS.json
```

训练时间：约10-30秒

### 6. 启动Dashboard

```bash
streamlit run streamlit_app/aps_dashboard.py
```

**访问地址：**
- 本地：http://localhost:8501
- 网络：http://<your-ip>:8501

按 `Ctrl+C` 停止服务

---

## � Linux服务器部署

### 方式一：使用打包脚本（推荐）

#### 1. 打包项目

在本地开发环境运行：

```bash
# 在项目根目录
./package.sh
```

生成文件：`sap-production-predictor-1.0.0-linux.tar.gz` (约248KB)

#### 2. 上传到Linux服务器

```bash
scp sap-production-predictor-1.0.0-linux.tar.gz user@server:/opt/
```

#### 3. 在服务器上解压并部署

```bash
cd /opt
tar -xzf sap-production-predictor-1.0.0-linux.tar.gz
cd sap-production-predictor
./deploy.sh
```

#### 4. 上传数据文件

```bash
scp data/raw/*.csv user@server:/opt/sap-production-predictor/data/raw/
```

#### 5. 启动服务

**快速启动：**
```bash
./start.sh
```

**使用systemd（生产推荐）：**
```bash
sudo cp config/sap-predictor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sap-predictor
sudo systemctl start sap-predictor
sudo systemctl status sap-predictor
```

#### 6. 配置防火墙

```bash
# Ubuntu/Debian
sudo ufw allow 8501/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

访问：http://服务器IP:8501

### 配置Nginx反向代理（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
sudo systemctl reload nginx
```

### Linux部署故障排查

**端口占用：**
```bash
sudo lsof -i :8501
sudo kill -9 <PID>
```

**查看服务日志：**
```bash
sudo journalctl -u sap-predictor -f
```

**内存不足（创建swap）：**
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```



## �📂 项目结构

```
sap-production-predictor/
├── data/
│   ├── raw/                      # 原始CSV数据
│   └── processed/                # 处理后的数据
├── models/                       # 训练好的模型文件
├── scripts/
│   ├── train_aps_model.py       # 模型训练脚本
│   └── show_results.py          # 结果展示脚本
├── src/
│   ├── data_processing/
│   │   ├── aps_data_loader.py   # 数据加载器
│   │   └── aps_feature_engineer.py  # 特征工程
│   ├── models/
│   │   └── xgboost_model.py     # XGBoost模型
│   └── database/
│       └── connection.py         # 数据库连接（可选）
├── streamlit_app/
│   └── aps_dashboard.py         # Dashboard主程序
├── requirements.txt              # 依赖清单
└── README.md                     # 项目说明
```

---

## 🔧 常见问题

### Q1: 训练时提示"未找到数据文件"

**解决方案：**
```bash
# 检查文件是否存在
ls -la data/raw/

# 确保至少有 History.csv
```

### Q2: Dashboard启动后无法访问

**解决方案：**
```bash
# 指定端口启动
streamlit run streamlit_app/aps_dashboard.py --server.port 8501

# 检查端口是否被占用
lsof -i :8501
```

### Q3: 模型加载失败（XGBoost错误）

**macOS用户：**
```bash
# 安装libomp
brew install libomp

# 或重新安装xgboost
pip uninstall xgboost
pip install xgboost --no-cache-dir
```

**其他系统：**
```bash
pip install --upgrade xgboost
```

### Q4: 内存不足

**解决方案：**
- 减少训练数据量（只使用最近6个月数据）
- 调整feature_engineer中的lookback_days参数
- 增加系统虚拟内存

### Q5: Supabase连接失败

Dashboard可以**不依赖Supabase**正常运行。

如需Supabase：
```bash
# 配置.env文件
cp .env.example .env
# 编辑.env，填入Supabase凭据
```

---

## 🎯 使用流程

1. **首次使用**
   ```bash
   # 1. 准备数据
   # 将CSV文件放入 data/raw/
   
   # 2. 训练模型
   python scripts/train_aps_model.py
   
   # 3. 启动Dashboard
   streamlit run streamlit_app/aps_dashboard.py
   ```

2. **日常使用**
   ```bash
   # 直接启动Dashboard即可
   streamlit run streamlit_app/aps_dashboard.py
   ```

3. **更新数据后重新训练**
   ```bash
   # 1. 更新data/raw/中的CSV文件
   # 2. 重新训练
   python scripts/train_aps_model.py
   # 3. 重启Dashboard
   ```

---

## 📊 Dashboard功能

Dashboard提供5个页面：

1. **🏠 总览Dashboard**
   - 核心KPI（订单量、延迟率等）
   - 延迟分布图表
   - 月度趋势分析

2. **📊 模型性能**
   - 准确率、精确率、召回率等指标
   - 混淆矩阵
   - 特征重要性排名

3. **🔮 实时预测**
   - 订单延迟风险评估
   - 风险等级分类
   - 智能建议

4. **⚠️ 风险物料**
   - 高风险物料识别
   - 延迟率筛选
   - 可视化分析

5. **📈 趋势分析**
   - 多时间粒度趋势
   - 生产负载分析

---

## 🔐 安全建议

1. **生产环境部署：**
   - 修改默认端口
   - 配置防火墙规则
   - 使用HTTPS（配置反向代理）

2. **数据安全：**
   - 定期备份 `data/` 和 `models/` 目录
   - 敏感数据加密存储
   - 限制文件访问权限

3. **凭据管理：**
   - 不要将 `.env` 文件提交到版本控制
   - 使用环境变量存储敏感信息

---

## 📞 技术支持

- **模型版本**: APS v1.0
- **训练数据**: 2024-01-02 至 2025-12-23
- **模型性能**: 91.2% 准确率，0.919 ROC AUC

如有问题，请联系项目维护人员。

---

## 📝 更新日志

### v1.0 (2025-12-24)
- ✅ 集成5个CSV文件数据源
- ✅ 创建36维特征工程
- ✅ 训练XGBoost延迟预测模型
- ✅ 开发Streamlit Dashboard
- ✅ 支持历史分析和实时预测

---

**部署完成后，访问 http://localhost:8501 开始使用！** 🎉
