#!/bin/bash
# 估值预警系统启动脚本

# 进入项目目录
cd "$(dirname "$0")"

# 检查依赖
echo "检查依赖..."
pip install -r requirements.txt -q

# 启动Streamlit
echo "启动估值预警系统..."
echo "访问地址: http://localhost:8501"
echo ""

streamlit run app.py --server.headless true
