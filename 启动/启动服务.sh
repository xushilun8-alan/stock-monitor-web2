#!/bin/bash
# stock-monitor-web2 启动脚本（Vue + Flask）
# 功能：检测已运行进程并重启，确保只有一组服务实例

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FLASK_LOG="$PROJECT_DIR/logs/flask_app.log"
VUE_LOG="$PROJECT_DIR/logs/vue_dev.log"
FLASK_PID_FILE="$PROJECT_DIR/启动/flask.pid"
VUE_PID_FILE="$PROJECT_DIR/启动/vue.pid"

mkdir -p "$PROJECT_DIR/logs"

# ── 跨平台：根据端口查 PID（支持 Linux/macOS，无 lsof 时降级）─
pid_by_port() {
    local port=$1
    # 优先用 lsof（Linux/macOS 均支持）
    if command -v lsof &>/dev/null; then
        lsof -t -i :$port 2>/dev/null | head -1
        return
    fi
    # 备选：用 ss（Linux）
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep ":$port " | grep -o 'pid=[0-9]*' | head -1 | sed 's/pid=//'
        return
    fi
}

# ── 安全终止进程（TERM → 等待3s → KILL）─
kill_safe() {
    local pid=$1 name=$2
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        return
    fi
    echo "  停止旧 $name (PID: $pid)..."
    kill "$pid" 2>/dev/null
    for i in 1 2 3; do
        sleep 1
        kill -0 "$pid" 2>/dev/null || { echo "  ✅ $name 已停止"; return; }
    done
    kill -9 "$pid" 2>/dev/null
    echo "  ⚡ $name 强制终止"
}

# ── 检查并停止旧 Flask ──
stop_old_flask() {
    local pid=""
    if [ -f "$FLASK_PID_FILE" ]; then
        pid=$(cat "$FLASK_PID_FILE")
    fi
    # 端口冲突检测（兜底）
    if [ -z "$pid" ]; then
        pid=$(pid_by_port 5188)
    fi
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill_safe "$pid" "Flask"
    fi
    rm -f "$FLASK_PID_FILE"
}

# ── 检查并停止旧 Vue ──
stop_old_vue() {
    local pid=""
    if [ -f "$VUE_PID_FILE" ]; then
        pid=$(cat "$VUE_PID_FILE")
    fi
    if [ -z "$pid" ]; then
        pid=$(pid_by_port 5173)
    fi
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill_safe "$pid" "Vue"
    fi
    rm -f "$VUE_PID_FILE"
}

echo "📊 股票监控系统启动"
echo "========================================"

# 先停止所有旧进程（确保干净重启）
echo "🛑 检查旧进程..."
stop_old_flask
stop_old_vue
sleep 1

# ── 创建/激活虚拟环境 ──
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "📦 创建虚拟环境..."
    /usr/local/bin/python3 -m venv "$PROJECT_DIR/.venv"
fi
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python3"
VENV_PIP="$PROJECT_DIR/.venv/bin/pip3"
$VENV_PIP install -r "$PROJECT_DIR/requirements.txt" -q 2>/dev/null

# ── 启动 Flask ──
echo "🚀 启动 Flask 后端 (端口 5188)..."
cd "$PROJECT_DIR"
nohup $VENV_PYTHON "$PROJECT_DIR/app.py" >> "$FLASK_LOG" 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > "$FLASK_PID_FILE"
sleep 3

if kill -0 "$FLASK_PID" 2>/dev/null; then
    echo "✅ Flask 启动成功 (PID: $FLASK_PID)"
else
    echo "❌ Flask 启动失败，请检查日志: $FLASK_LOG"
    tail -10 "$FLASK_LOG"
fi

# ── 安装/启动 Vue ──
if [ ! -d "$PROJECT_DIR/vue-project/node_modules" ]; then
    echo "📦 安装 Vue 依赖..."
    cd "$PROJECT_DIR/vue-project"
    npm install --silent 2>/dev/null
fi

echo "🚀 启动 Vue 开发服务器 (端口 5173)..."
cd "$PROJECT_DIR/vue-project"
nohup npm run dev -- --host 0.0.0.0 >> "$VUE_LOG" 2>&1 &
VUE_PID=$!
echo $VUE_PID > "$VUE_PID_FILE"
sleep 3

if kill -0 "$VUE_PID" 2>/dev/null; then
    echo "✅ Vue Dev Server 启动成功 (PID: $VUE_PID)"
else
    echo "❌ Vue 启动失败，请检查日志: $VUE_LOG"
fi

echo ""
echo "========================================"
echo "✅ 服务已启动"
echo "   Vue 前端: http://localhost:5173"
echo "   Flask API: http://localhost:5188"
echo "========================================"
