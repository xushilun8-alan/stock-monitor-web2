# stock-monitor-web2 服务管理

## 📁 文件说明

| 文件 | 功能 |
|------|------|
| `启动服务.sh` | 在后台启动 Flask + Vue 双服务 |
| `停止服务.sh` | 停止所有后台运行的服务 |
| `查看状态.sh` | 检查服务运行状态 |

## 🚀 使用方法

### 启动服务
```bash
cd /Users/xusl/openclaw_projects/stock-monitor-web2/启动
./启动服务.sh
```
或直接双击 `启动服务.sh`

### 停止服务
```bash
cd /Users/xusl/openclaw_projects/stock-monitor-web2/启动
./停止服务.sh
```

### 查看状态
```bash
cd /Users/xusl/openclaw_projects/stock-monitor-web2/启动
./查看状态.sh
```

## 📊 服务信息

| 服务 | 地址 | PID 文件 |
|------|------|---------|
| Vue 前端 | http://localhost:5173 | `启动/vue.pid` |
| Flask API | http://localhost:5188 | `启动/flask.pid` |

- **日志文件**: `logs/flask_app.log` / `logs/vue_dev.log`
- **PID 文件**: `启动/flask.pid` / `启动/vue.pid`

## ⚠️ 注意事项

- 首次使用需添加执行权限: `chmod +x *.sh`
- 双击运行 macOS 可能提示"无法运行"——右键打开或 `chmod +x`
- 改代码后，彻底清除进程：
  ```bash
  pkill -f "stock-monitor-web2/app.py"
  pkill -f "vite"
  ```
