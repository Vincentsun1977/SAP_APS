# SAP Production Delay Predictor

<div align="center">

**基于XGBoost的SAP生产延迟预测系统**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-orange.svg)](https://xgboost.ai/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*SAP Production Delay Prediction with XGBoost and Streamlit Dashboard*

[English](#english) | [中文](#中文)

</div>

---

## 中文

### 📊 项目简介

基于机器学习的SAP生产订单延迟预测系统，使用XGBoost算法分析历史生产数据，预测订单延迟风险，帮助企业提前采取行动，优化生产排程。

**核心功能：**
- 🤖 **智能预测** - 预测实际生产天数（RMSE=1.75天，CV R²=0.37），辅助延迟风险判断
- 📊 **可视化Dashboard** - Streamlit交互式分析面板
- 📈 **特征工程** - 54维自动化特征生成（含缺料数据）
- ⚠️ **风险识别** - 高风险物料和订单识别
- 📉 **趋势分析** - 多维度生产延迟趋势
- 🔗 **SAP缺料集成** - 自动读取Shortage.csv提升预测精度

### ✨ 主要特性

#### 数据整合
- 支持6个CSV文件数据源（Order, FG, Capacity, APS, History, **Shortage**）
- 自动数据合并和清洗
- 2,487条历史订单训练数据（过滤离群值后）

#### 模型性能（v2，2026-04-15）
- **Test RMSE**: 1.751 天
- **Test MAE**: 1.113 天
- **Test R²**: 0.313
- **CV R²**: 0.374 ± 0.136（5折时序交叉验证）

#### Dashboard功能
- 🏠 总览Dashboard - 核心KPI和趋势
- 📊 模型性能分析 - 混淆矩阵、特征重要性
- 🔮 实时预测 - 订单延迟风险评估
- ⚠️ 风险物料识别 - 高延迟率物料筛选
- 📈 趋势分析 - 多时间粒度分析

### 🚀 快速开始

#### 1. 克隆项目

```bash
git clone https://github.com/Vincentsun1977/sap-production-delay-predictor.git
cd sap-production-delay-predictor
```

#### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

#### 2.5 配置PostgreSQL（新）

1. 在 `.env` 或环境变量中设置以下键：`POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_SCHEMA`、`POSTGRES_SSL_MODE`（示例值已提供）。
2. 启动本地 PostgreSQL（至少 14+），确保可以使用上面的凭据连接，SSL 可在本地关闭。
3. 运行 `python scripts/init_database.py` 自动创建 `raw_orders`、`features`、`predictions`、`model_metadata` 等表。
4. 训练脚本会自动将模型元数据、特征等写入 PostgreSQL，无需再配置 Supabase。

#### 3. 准备数据

将以下CSV文件放入 `data/raw/` 目录：

```
data/raw/
├── History.csv     # 历史生产订单（必需）
├── Order.csv       # 客户订单
├── FG.csv          # 成品物料主数据
├── Capacity.csv    # 产线产能
└── APS.csv         # APS生产计划
```

**History.csv 必须包含字段：**
- Sales Order（销售订单号）
- Order（生产订单号）
- Material Number（物料号）
- Basic start date（计划开始）
- Basic finish date（计划完成）
- **Actual finish date（实际完成）** ← 必需！

#### 4. 训练模型

```bash
python scripts/train_aps_model.py
```

预期输出：
```
✓ 加载了 2,491 条历史订单
✓ 模型准确率: 91.2%
✓ 模型已保存
```

#### 5. 启动Dashboard

```bash
streamlit run streamlit_app/aps_dashboard.py
```

访问 http://localhost:8501

### 📂 项目结构

```
sap-production-predictor/
├── data/
│   ├── raw/                      # 原始CSV数据
│   └── processed/                # 处理后的数据
├── models/                       # 训练好的模型
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
│       └── connection.py         # 数据库连接
├── streamlit_app/
│   └── aps_dashboard.py         # Dashboard主程序
├── DEPLOYMENT.md                 # 部署文档
├── FEATURES_AND_LABELS.md       # 特征说明
└── requirements.txt              # 依赖清单
```

### 🎯 特征说明（v2）

模型使用54个特征进行预测，分为9大类：

| 类别 | 特征数 | 示例 |
|------|--------|------|
| 基础订单特征 | 8 | 计划生产天数、订单数量、log变换 |
| 时间特征 | 11 | 季度、星期、月初月末 |
| 物料与复杂度 | 5 | 复杂度、MRP控制员、约束 |
| 并发工作负载⭐ | 4 | 创建-开始间隔、并发订单数 |
| 历史生产时长⭐ | 7 | 物料90天均值/标准差（因果扩展均值） |
| 目标编码 | 1 | 物料平均生产时长 |
| 缺料特征⭐ | 7 | 缺料比例、缺料组件数（来自Shortage.csv） |
| 产能特征 | 3 | 产能利用率、工作强度 |
| 交互特征 | 8 | 缺料×订单量、复杂度×产能 |

**Top 5 最重要特征（v2）：**
1. `earliest_start_days`（最早开工等待天数，重要性0.183）
2. `total_production_time`（单位生产时长，重要性0.137）
3. `create_to_start_gap`（创建到开始间隔，重要性0.133）
4. `shortage_qty_ratio`（缺料数量占需求比例，重要性0.058）⭐
5. `shortage_component_count`（缺料组件数，重要性0.029）⭐

详见 [FEATURES_AND_LABELS.md](FEATURES_AND_LABELS.md)

### 🐧 Linux服务器部署

#### 快速部署

```bash
# 1. 打包项目
./package.sh

# 2. 上传到服务器
scp sap-production-predictor-1.0.0-linux.tar.gz user@server:/opt/

# 3. 在服务器上解压并部署
cd /opt
tar -xzf sap-production-predictor-1.0.0-linux.tar.gz
cd sap-production-predictor
./deploy.sh

# 4. 启动服务（使用systemd）
sudo cp config/sap-predictor.service /etc/systemd/system/
sudo systemctl enable sap-predictor
sudo systemctl start sap-predictor
```

详见 [DEPLOYMENT.md](DEPLOYMENT.md)

### 📊 使用示例

#### 预测示例
```python
from src.models.xgboost_model import ProductionDelayModel

# 加载模型
model = ProductionDelayModel()
model.load("models/aps_xgb_model_latest.json")

# 预测延迟概率
delay_prob = model.predict_proba(X_new)[:, 1]
print(f"延迟概率: {delay_prob[0]:.1%}")

# 输出: 延迟概率: 23.5%
```

### 🛠️ 技术栈

- **语言**: Python 3.9+
- **机器学习**: XGBoost 2.0, scikit-learn
- **数据处理**: Pandas, NumPy
- **可视化**: Streamlit, Plotly
- **数据库**: Supabase (可选)
- **日志**: Loguru

### 📈 模型性能（v2，2026-04-15）

基于2,487条历史订单（过滤离群值后），时序分割评估：

| 数据集 | RMSE | MAE | R² |
|--------|------|-----|----|
| 训练集 | 1.155 天 | 0.819 天 | 0.748 |
| **测试集** | **1.751 天** | **1.113 天** | **0.313** |
| **5折CV** | **1.701 ± 0.218 天** | **1.141 ± 0.110 天** | **0.374 ± 0.136** |

**数据分布：**
- 训练样本：2,487 条（过滤异常值后）
- 延迟订单：370 (14.9%)
- 预测目标：实际生产天数（均值2.95天，中位数2天）

### 🔧 常见问题

**Q: 如何获取训练数据？**  
A: 从SAP系统导出生产订单历史数据，包含实际完成日期。

**Q: 模型多久需要重新训练？**  
A: 建议每月或每季度重新训练，或当新增大量数据时。

**Q: 可以预测多久之后的订单？**  
A: 模型基于历史模式，适用于计划开始日期在未来的订单。

**Q: 如何提高召回率？**  
A: 调整分类阈值（默认0.5）或使用SMOTE处理类别不平衡。

### 🤝 贡献

欢迎贡献！请：
1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

### 📞 联系方式

如有问题或建议，请提交 [Issue](https://github.com/Vincentsun1977/sap-production-delay-predictor/issues)

---

## English

### 📊 Overview

A machine learning-based SAP production order delay prediction system using XGBoost algorithm to analyze historical production data and predict order delay risks, helping enterprises take proactive actions and optimize production scheduling.

**Key Features:**
- 🤖 **Smart Prediction** - 84.8% accuracy, 83.8% recall delay prediction model
- 📈 **Visual Dashboard** - Streamlit interactive analysis panel
- 📈 **Feature Engineering** - 36-dimensional automated feature generation
- ⚠️ **Risk Identification** - High-risk materials and orders identification
- 📉 **Trend Analysis** - Multi-dimensional production delay trends

### ✨ Highlights

- **High Accuracy**: 84.8% accuracy, 0.902 ROC AUC, 83.8% recall
- **5 Data Sources**: Integrates Order, FG, Capacity, APS, History CSV files
- **36 Features**: Automatic generation of predictive features
- **Interactive Dashboard**: 5 functional pages for comprehensive analysis
- **Production Ready**: Includes Linux deployment package and systemd service

### 🚀 Quick Start

See [Chinese section](#中文) for detailed instructions.

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/sap-production-delay-predictor.git

# Install
pip install -r requirements.txt

# Train
python scripts/train_aps_model.py

# Launch Dashboard
streamlit run streamlit_app/aps_dashboard.py
```

### 📈 Model Performance

| Metric | Score |
|--------|-------|
| Accuracy | 84.8% |
| Precision | 49.2% |
| Recall | 83.8% |
| F1 Score | 0.620 |
| ROC AUC | 0.902 |

### 🛠️ Tech Stack

- Python 3.9+, XGBoost 2.0, Streamlit, Plotly
- Pandas, NumPy, scikit-learn
- Supabase (optional)

### 📄 License

MIT License - see [LICENSE](LICENSE)

---

<div align="center">

**⭐ Star this repo if you find it helpful!**

Made with ❤️ for SAP Production Planning

</div>
