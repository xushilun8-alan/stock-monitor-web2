#!/bin/bash
# stock-monitor-web2 停止脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FLASK_PID_FILE="$PROJECT_DIR/启动/flask.pid"
VUE_PID_FILE="$PROJECT_DIR/启动/vue.pid"

kill_safe() {
    local pid=$1 name=$2
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        echo "  ⚠️  $name 未运行"
        return
    fi
    echo "  停止 $name (PID: $pid)..."
    kill "$pid" 2>/dev/null
    for i in 1 2 3; do
        sleep 1
        kill -0 "$pid" 2>/dev/null || { echo "  ✅ $name 已停止"; return; }
    done
    kill -9 "$pid" 2>/dev/null
    echo "  ⚡ $name 强制终止 (PID: $pid)"
}

echo "🛑 停止服务..."
echo "========================================"

# 读 PID 文件
FLASK_PID=""
VUE_PID=""
[ -f "$FLASK_PID_FILE" ] && FLASK_PID=$(cat "$FLASK_PID_FILE")
[ -f "$VUE_PID_FILE" ] && VUE_PID=$(cat "$VUE_PID_FILE")

kill_safe "$FLASK_PID" "Flask (5188)"
kill_safe "$VUE_PID" "Vue Dev Server (5173)"

# 兜底：用 ps 查找残留进程
for proc in flask app.py vue; do
    EXTRA=$(ps aux 2>/dev/null | grep -i "$proc" | grep -v grep | awk '{print $2}')
    for pid in $EXTRA; do
        echo "  🧹 清理残留进程 (PID: $pid)..."
        kill -9 "$pid" 2>/dev/null
    done
done

rm -f "$FLASK_PID_FILE" "$VUE_PID_FILE"
echo "========================================"
echo "✅ 所有服务已停止"
