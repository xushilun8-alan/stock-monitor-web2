#!/bin/bash
# stock-monitor-web2 停止脚本
# 功能：停止后台运行的 Flask + Vue 服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FLASK_PID_FILE="$PROJECT_DIR/启动/flask.pid"
VUE_PID_FILE="$PROJECT_DIR/启动/vue.pid"

stop_service() {
    local name=$1
    local pid_file=$2
    local port=$3

    local PID=""
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
    fi

    if [ -z "$PID" ]; then
        PID=$(lsof -ti:$port 2>/dev/null | head -1)
    fi

    if [ -z "$PID" ]; then
        echo "⚠️  $name 未运行"
        return
    fi

    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        sleep 1
        if kill -0 "$PID" 2>/dev/null; then
            echo "⚠️  强制停止 $name (PID: $PID)..."
            kill -9 "$PID" 2>/dev/null
        fi
        echo "✅ $name 已停止 (PID: $PID)"
    else
        echo "⚠️  $name 进程不存在"
    fi

    rm -f "$pid_file"
}

echo "🛑 停止服务..."
stop_service "Flask (5188)" "$FLASK_PID_FILE" 5188
stop_service "Vue Dev Server (5173)" "$VUE_PID_FILE" 5173

echo ""
echo "✅ 所有服务已停止"
