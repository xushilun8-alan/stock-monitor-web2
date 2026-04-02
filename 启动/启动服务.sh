#!/bin/bash
# stock-monitor-web2 启动脚本（Vue + Flask）
# 功能：在后台启动 Flask + Vue 双服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FLASK_LOG="$PROJECT_DIR/logs/flask_app.log"
VUE_LOG="$PROJECT_DIR/logs/vue_dev.log"
FLASK_PID_FILE="$PROJECT_DIR/启动/flask.pid"
VUE_PID_FILE="$PROJECT_DIR/启动/vue.pid"

mkdir -p "$PROJECT_DIR/logs"

# ── 检查 Flask 是否已运行 ──
if [ -f "$FLASK_PID_FILE" ]; then
    OLD_PID=$(cat "$FLASK_PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  Flask 已在运行 (PID: $OLD_PID)"
    else
        rm -f "$FLASK_PID_FILE"
    fi
fi

# ── 检查 Vue 是否已运行 ──
if [ -f "$VUE_PID_FILE" ]; then
    OLD_PID=$(cat "$VUE_PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  Vue Dev Server 已在运行 (PID: $OLD_PID)"
    else
        rm -f "$VUE_PID_FILE"
    fi
fi

# ── 创建虚拟环境（如不存在）─
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    /usr/local/bin/python3 -m venv "$PROJECT_DIR/.venv"
fi
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python3"
VENV_PIP="$PROJECT_DIR/.venv/bin/pip3"
$VENV_PIP install -r "$PROJECT_DIR/requirements.txt" -q

# ── 启动 Flask ──
echo "🚀 启动 Flask 后端 (端口 5188)..."
cd "$PROJECT_DIR"
nohup $VENV_PYTHON "$PROJECT_DIR/app.py" > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > "$FLASK_PID_FILE"
echo $FLASK_PID > "$PROJECT_DIR/启动/flask.pid"
sleep 2

if kill -0 "$FLASK_PID" 2>/dev/null; then
    echo "✅ Flask 启动成功 (PID: $FLASK_PID)"
else
    echo "❌ Flask 启动失败，请检查日志: $FLASK_LOG"
fi

# ── 安装 Vue 依赖 ──
if [ ! -d "$PROJECT_DIR/vue-project/node_modules" ]; then
    echo "📦 安装 Vue 依赖..."
    cd "$PROJECT_DIR/vue-project"
    npm install --silent
fi

# ── 启动 Vue Dev Server ──
echo "🚀 启动 Vue 开发服务器 (端口 5173)..."
cd "$PROJECT_DIR/vue-project"
nohup npm run dev -- --host 0.0.0.0 > "$VUE_LOG" 2>&1 &
VUE_PID=$!
echo $VUE_PID > "$VUE_PID_FILE"
echo $VUE_PID > "$PROJECT_DIR/启动/vue.pid"
sleep 3

if kill -0 "$VUE_PID" 2>/dev/null; then
    echo "✅ Vue Dev Server 启动成功 (PID: $VUE_PID)"
else
    echo "❌ Vue Dev Server 启动失败，请检查日志: $VUE_LOG"
fi

echo ""
echo "========================================"
echo "✅ 服务已全部启动"
echo "   Vue 前端: http://localhost:5173"
echo "   Flask API: http://localhost:5188"
echo "========================================"
echo "   Flask 日志: $FLASK_LOG"
echo "   Vue 日志:   $VUE_LOG"
