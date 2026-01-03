#!/bin/bash
# SAP Production Predictor - 项目打包脚本
# 用于创建Linux服务器部署包

set -e

echo "================================================"
echo "  SAP生产延迟预测系统 - 打包脚本"
echo "================================================"

# 配置
PACKAGE_NAME="sap-production-predictor"
VERSION="1.0.0"
BUILD_DIR="build"
PACKAGE_DIR="${BUILD_DIR}/${PACKAGE_NAME}"
ARCHIVE_NAME="${PACKAGE_NAME}-${VERSION}-linux.tar.gz"

# 清理旧的构建
echo "📦 清理旧的构建文件..."
rm -rf ${BUILD_DIR}
mkdir -p ${PACKAGE_DIR}

# 创建目录结构
echo "📁 创建目录结构..."
mkdir -p ${PACKAGE_DIR}/{data/{raw,processed},models,logs,config}

# 复制源代码
echo "📄 复制源代码..."
cp -r src ${PACKAGE_DIR}/
cp -r scripts ${PACKAGE_DIR}/
cp -r streamlit_app ${PACKAGE_DIR}/

# 复制配置文件
echo "⚙️  复制配置文件..."
cp requirements.txt ${PACKAGE_DIR}/
cp DEPLOYMENT.md ${PACKAGE_DIR}/
cp README.md ${PACKAGE_DIR}/ 2>/dev/null || echo "README.md not found, skipping..."
cp .env.example ${PACKAGE_DIR}/ 2>/dev/null || echo ".env.example not found, skipping..."

# 复制已训练的模型（如果存在）
echo "🤖 复制训练好的模型..."
if [ -d "models" ] && [ "$(ls -A models/*.json 2>/dev/null)" ]; then
    cp models/*.json ${PACKAGE_DIR}/models/ 2>/dev/null || true
    echo "  ✓ 已复制模型文件"
else
    echo "  ⚠ 未找到模型文件，需要在服务器上重新训练"
fi

# 复制处理后的数据（可选）
if [ -d "data/processed" ] && [ "$(ls -A data/processed/*.csv 2>/dev/null)" ]; then
    cp data/processed/*.csv ${PACKAGE_DIR}/data/processed/ 2>/dev/null || true
    echo "  ✓ 已复制处理后的数据"
fi

# 创建Linux部署脚本
echo "🚀 创建部署脚本..."
cat > ${PACKAGE_DIR}/deploy.sh << 'EOF'
#!/bin/bash
# Linux服务器部署脚本

set -e

echo "================================================"
echo "  SAP生产延迟预测系统 - 自动部署"
echo "================================================"

# 检查Python版本
echo "🔍 检查Python版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  ✓ Python版本: $PYTHON_VERSION"

# 创建虚拟环境
echo "🔧 创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 升级pip
echo "⬆️  升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📦 安装Python依赖..."
pip install -r requirements.txt

# 创建.env文件（如果不存在）
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "  ✓ 已创建.env配置文件，请编辑填入实际配置"
    fi
fi

# 检查数据文件
echo "📊 检查数据文件..."
if [ ! -f "data/raw/History.csv" ]; then
    echo "  ⚠️  警告: 未找到 data/raw/History.csv"
    echo "  请将CSV文件放入 data/raw/ 目录"
fi

# 检查模型文件
echo "🤖 检查模型文件..."
if ! ls models/*.json 1> /dev/null 2>&1; then
    echo "  ⚠️  警告: 未找到训练好的模型"
    echo "  请运行: python scripts/train_aps_model.py"
fi

echo ""
echo "================================================"
echo "✅ 部署完成！"
echo "================================================"
echo ""
echo "📝 下一步操作："
echo "  1. 将CSV数据文件放入: data/raw/"
echo "  2. 训练模型: python scripts/train_aps_model.py"
echo "  3. 启动Dashboard: streamlit run streamlit_app/aps_dashboard.py"
echo ""
echo "或使用systemd服务（推荐）："
echo "  sudo cp config/sap-predictor.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable sap-predictor"
echo "  sudo systemctl start sap-predictor"
echo ""
EOF

chmod +x ${PACKAGE_DIR}/deploy.sh

# 创建systemd服务文件
echo "⚙️  创建systemd服务文件..."
cat > ${PACKAGE_DIR}/config/sap-predictor.service << EOF
[Unit]
Description=SAP Production Delay Predictor Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/sap-production-predictor
Environment="PATH=/opt/sap-production-predictor/venv/bin"
ExecStart=/opt/sap-production-predictor/venv/bin/streamlit run streamlit_app/aps_dashboard.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 创建启动脚本
cat > ${PACKAGE_DIR}/start.sh << 'EOF'
#!/bin/bash
# 快速启动脚本

source venv/bin/activate
streamlit run streamlit_app/aps_dashboard.py --server.port 8501 --server.address 0.0.0.0
EOF

chmod +x ${PACKAGE_DIR}/start.sh

# 创建停止脚本
cat > ${PACKAGE_DIR}/stop.sh << 'EOF'
#!/bin/bash
# 停止服务脚本

pkill -f "streamlit run streamlit_app/aps_dashboard.py"
echo "✓ Dashboard已停止"
EOF

chmod +x ${PACKAGE_DIR}/stop.sh

# 创建README for deployment
cat > ${PACKAGE_DIR}/QUICKSTART.md << 'EOF'
# 快速开始指南

## Linux服务器部署

### 1. 解压文件
```bash
tar -xzf sap-production-predictor-*.tar.gz
cd sap-production-predictor
```

### 2. 自动部署
```bash
chmod +x deploy.sh
./deploy.sh
```

### 3. 准备数据
将以下CSV文件放入 `data/raw/` 目录：
- Order.csv
- FG.csv
- Capacity.csv
- APS.csv
- History.csv（必需）

### 4. 训练模型
```bash
source venv/bin/activate
python scripts/train_aps_model.py
```

### 5. 启动Dashboard

**方式A：直接启动**
```bash
./start.sh
```

**方式B：使用systemd（推荐）**
```bash
# 安装服务
sudo cp config/sap-predictor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sap-predictor
sudo systemctl start sap-predictor

# 查看状态
sudo systemctl status sap-predictor

# 查看日志
sudo journalctl -u sap-predictor -f
```

### 6. 访问Dashboard
打开浏览器访问：
- http://<服务器IP>:8501

### 停止服务
```bash
# 方式A
./stop.sh

# 方式B（使用systemd）
sudo systemctl stop sap-predictor
```

## 防火墙配置

如果无法访问Dashboard，可能需要开放端口：

```bash
# Ubuntu/Debian
sudo ufw allow 8501

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

## 故障排查

### 问题1: 端口已被占用
```bash
# 查看占用端口的进程
lsof -i :8501

# 更换端口启动
streamlit run streamlit_app/aps_dashboard.py --server.port 8502
```

### 问题2: 权限问题
```bash
# 给予执行权限
chmod +x deploy.sh start.sh stop.sh
```

### 问题3: 内存不足
编辑 `streamlit_app/aps_dashboard.py`，在文件开头添加：
```python
import os
os.environ['STREAMLIT_SERVER_MAX_UPLOAD_SIZE'] = '200'
```

更多帮助请参考 `DEPLOYMENT.md`
EOF

# 创建.gitignore（防止敏感文件被打包）
cat > ${PACKAGE_DIR}/.gitignore << 'EOF'
venv/
__pycache__/
*.pyc
.env
.DS_Store
*.log
data/raw/*.csv
.vscode/
.idea/
EOF

# 打包
echo "📦 创建归档文件..."
cd ${BUILD_DIR}
tar -czf ../${ARCHIVE_NAME} ${PACKAGE_NAME}/
cd ..

# 计算大小
SIZE=$(du -h ${ARCHIVE_NAME} | cut -f1)

echo ""
echo "================================================"
echo "✅ 打包完成！"
echo "================================================"
echo "📦 文件: ${ARCHIVE_NAME}"
echo "📊 大小: ${SIZE}"
echo "📂 位置: $(pwd)/${ARCHIVE_NAME}"
echo ""
echo "🚀 部署到Linux服务器："
echo "  1. 上传文件:"
echo "     scp ${ARCHIVE_NAME} user@server:/opt/"
echo ""
echo "  2. 在服务器上解压:"
echo "     tar -xzf ${ARCHIVE_NAME}"
echo "     cd ${PACKAGE_NAME}"
echo ""
echo "  3. 运行部署脚本:"
echo "     ./deploy.sh"
echo ""
echo "详细说明请查看包内的 QUICKSTART.md"
echo "================================================"
