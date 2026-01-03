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
- 🤖 **智能预测** - 91.2%准确率的延迟预测模型
- 📊 **可视化Dashboard** - Streamlit交互式分析面板
- 📈 **特征工程** - 36维自动化特征生成
- ⚠️ **风险识别** - 高风险物料和订单识别
- 📉 **趋势分析** - 多维度生产延迟趋势

### ✨ 主要特性

#### 数据整合
- 支持5个CSV文件数据源（Order, FG, Capacity, APS, History）
- 自动数据合并和清洗
- 2,491条历史订单训练数据

#### 模型性能
- **准确率**: 91.2%
- **ROC AUC**: 0.919
- **精确率**: 92.2%
- **召回率**: 44.6%

#### Dashboard功能
- 🏠 总览Dashboard - 核心KPI和趋势
- 📊 模型性能分析 - 混淆矩阵、特征重要性
- 🔮 实时预测 - 订单延迟风险评估
- ⚠️ 风险物料识别 - 高延迟率物料筛选
- 📈 趋势分析 - 多时间粒度分析

### 🚀 快速开始

#### 1. 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/sap-production-delay-predictor.git
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

### 🎯 特征说明

模型使用36个特征进行预测，分为6大类：

| 类别 | 特征数 | 示例 |
|------|--------|------|
| 基础特征 | 13 | 计划生产天数、订单数量、产能比 |
| 时间特征 | 6 | 是否周末、月初、季度末 |
| 物料特征 | 4 | 物料族、产品类型 |
| 产线特征 | 4 | 产线编码、生产复杂度 |
| 历史特征⭐ | 5 | 物料/产线历史延迟率 |
| 交互特征 | 4 | 复杂度×产能、数量×时间 |

**Top 5 最重要特征：**
1. material_delay_rate_90d（物料90天历史延迟率）
2. planned_start_quarter（计划开始季度）
3. planned_start_weekday（计划开始星期）
4. complexity_capacity_interaction（复杂度×产能）
5. qty_time_interaction（数量×时间）

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

### 📈 模型性能

基于2,491条历史订单（2024-01-02 至 2025-12-23）:

| 指标 | 分数 |
|------|------|
| 准确率 | 91.2% |
| 精确率 | 92.2% |
| 召回率 | 44.6% |
| F1 Score | 0.601 |
| ROC AUC | 0.919 |

**延迟率分布：**
- 延迟订单：370 (14.9%)
- 准时订单：2,121 (85.1%)

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

如有问题或建议，请提交 [Issue](https://github.com/YOUR_USERNAME/sap-production-delay-predictor/issues)

---

## English

### 📊 Overview

A machine learning-based SAP production order delay prediction system using XGBoost algorithm to analyze historical production data and predict order delay risks, helping enterprises take proactive actions and optimize production scheduling.

**Key Features:**
- 🤖 **Smart Prediction** - 91.2% accuracy delay prediction model
- 📊 **Visual Dashboard** - Streamlit interactive analysis panel
- 📈 **Feature Engineering** - 36-dimensional automated feature generation
- ⚠️ **Risk Identification** - High-risk materials and orders identification
- 📉 **Trend Analysis** - Multi-dimensional production delay trends

### ✨ Highlights

- **High Accuracy**: 91.2% accuracy, 0.919 ROC AUC
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
| Accuracy | 91.2% |
| Precision | 92.2% |
| Recall | 44.6% |
| F1 Score | 0.601 |
| ROC AUC | 0.919 |

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
