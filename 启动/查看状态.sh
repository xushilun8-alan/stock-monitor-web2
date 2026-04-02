#!/bin/bash
# stock-monitor-web2 状态检查脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FLASK_PID_FILE="$PROJECT_DIR/启动/flask.pid"
VUE_PID_FILE="$PROJECT_DIR/启动/vue.pid"

check_service() {
    local name=$1
    local pid_file=$2
    local port=$3

    local PID=""
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
    fi

    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "✅ $name 运行中 (PID: $PID)"
        return 0
    fi

    local alt_pid=$(lsof -ti:$port 2>/dev/null | head -1)
    if [ -n "$alt_pid" ]; then
        echo "✅ $name 运行中 (PID: $alt_pid) [未通过 PID 文件管理]"
        return 0
    fi

    echo "❌ $name 未运行"
    return 1
}

echo "📊 服务状态检查"
echo "========================"
check_service "Flask (5188)" "$FLASK_PID_FILE" 5188
check_service "Vue Dev Server (5173)" "$VUE_PID_FILE" 5173
echo "========================"
echo "   Vue 前端: http://localhost:5173"
echo "   Flask API: http://localhost:5188"
