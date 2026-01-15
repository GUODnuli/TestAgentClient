#!/bin/bash
# MCP 接口测试智能体 - 安装脚本（Linux/Mac）

set -e

echo "================================"
echo "MCP 接口测试智能体 - 安装程序"
echo "================================"

# 检查 Python 版本
echo "检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "检测到 Python $python_version"

# 安装后端依赖
echo "安装后端依赖..."
pip3 install -r requirements.txt

# 复制配置文件
echo "初始化配置文件..."
cd config
for file in *.example; do
    target="${file%.example}"
    if [ ! -f "$target" ]; then
        cp "$file" "$target"
        echo "已创建: $target"
    fi
done
cd ..

# 创建数据目录
echo "创建数据目录..."
mkdir -p data/uploads data/vectordb data/logs

echo "================================"
echo "安装完成！"
echo "================================"
echo ""
echo "下一步："
echo "1. 编辑 config/dify.toml 配置 Dify API 密钥"
echo "2. 运行 ./scripts/start.sh 启动服务"
