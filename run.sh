#!/usr/bin/env bash
# run.sh — 启动股票监控系统（Flask 后端 + Vue 开发服务器）
# 用法: ./run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "📊 股票监控系统启动"
echo "========================================"

# 检查端口占用
check_port() {
  if lsof -i :5188 > /dev/null 2>&1; then
    echo "⚠️  端口 5188 已被占用，Flask 可能已在运行"
  fi
  if lsof -i :5173 > /dev/null 2>&1; then
    echo "⚠️  端口 5173 已被占用，Vue dev server 可能已在运行"
  fi
}

check_port

# 启动 Flask 后端（后台）
echo "🚀 启动 Flask 后端 (端口 5188)..."
python3 app.py &
FLASK_PID=$!
sleep 2

# 启动 Vue 开发服务器（后台）
echo "🚀 启动 Vue 开发服务器 (端口 5173)..."
cd vue-project
npm install --silent 2>/dev/null || true
npm run dev &
VUE_PID=$!

echo ""
echo "========================================"
echo "✅ 服务已启动"
echo "   Vue 前端: http://localhost:5173"
echo "   Flask API: http://localhost:5188"
echo "========================================"
echo "按 Ctrl+C 停止所有服务"
echo ""

# 捕获退出信号，停止后台进程
trap "kill $FLASK_PID $VUE_PID 2>/dev/null; echo '已停止所有服务'; exit 0" SIGINT SIGTERM

# 等待子进程
wait
