# 项目模块文档

## 目录结构

```
stock-monitor-web2/
├── run.sh                      # 双服务启动脚本（Flask + Vue）
├── app.py                      # Flask 应用工厂 + 页面渲染路由
├── run.py                      # Flask 启动入口（兼容）
├── models.py                   # 兼容重导出 → models/
├── monitor.py                  # 兼容重导出 → services/monitor/
├── feishu_notifier.py          # 兼容重导出 → services/feishu_notifier/
├── stock_data.py               # 兼容重导出 → services/stock_data/
│
├── models/                     # 数据库模型层
│   ├── __init__.py             # init_db() + 所有 CRUD 函数
│   └── MODULES.md              # 本模块详细文档
│
├── services/                   # 业务服务层
│   ├── __init__.py             # 包索引
│   ├── stock_data.py           # 股价数据获取（腾讯/新浪/Yahoo 三源）
│   ├── feishu_notifier.py      # 飞书通知发送
│   ├── monitor.py              # 后台监控调度
│   └── SERVICES.md             # 本模块详细文档
│
├── routes/                     # API 路由层
│   ├── __init__.py             # Blueprint 注册
│   ├── stock_api.py            # 所有 /api/* 接口
│   └── ROUTES.md              # 本模块详细文档
│
├── vue-project/               # Vue 3 前端（SPA）
│   ├── src/
│   │   ├── main.js            # Vue 入口
│   │   ├── App.vue            # 根组件
│   │   ├── api/
│   │   │   └── stocks.js      # API 客户端
│   │   ├── stores/
│   │   │   └── stockStore.js  # Pinia 状态管理
│   │   ├── composables/
│   │   │   ├── useToast.js    # Toast 通知 composable
│   │   │   └── useModal.js    # 弹窗 composable
│   │   ├── components/
│   │   │   ├── StockTable.vue    # 监控列表表格
│   │   │   ├── DeletedTable.vue  # 回收站表格
│   │   │   ├── StockModal.vue    # 添加/编辑弹窗
│   │   │   ├── ConfirmModal.vue  # 删除确认弹窗
│   │   │   ├── DestroyModal.vue  # 彻底删除确认弹窗
│   │   │   ├── IntervalBar.vue   # 全局监控频率设置栏
│   │   │   ├── ToastNotification.vue # Toast 通知组件
│   │   │   └── NavTabs.vue       # 导航标签页
│   │   └── styles/
│   │       └── main.css       # 全局样式
│   ├── vite.config.js         # Vite 配置（含 /api 代理
│   ├── package.json
│   └── index.html
│
├── templates/                  # Flask 模板（空，Vue SPA 替代）
├── static/                     # 静态资源
├── logs/                       # 日志文件夹
│   ├── __init__.py             # 包索引
│   ├── logger.py               # 日志记录工具
│   ├── api_errors.log          # API 接口报错日志
│   ├── frontend_errors.log     # 前端操作报错日志
│   └── stock_updates.log       # 股票信息变更记录
│
└── data/                       # 数据持久化
    ├── stocks.db               # SQLite 数据库
    └── notification_status.json # 飞书通知去重状态
```

## 模块职责

| 模块 | 职责 | 关键接口 |
|------|------|---------|
| **models** | SQLite 封装，股票 CRUD，软删除/恢复 | `get_all_stocks`, `add_stock`, `update_stock`, `delete_stock`, `restore_stock` |
| **services/stock_data** | 腾讯/新浪财经/Yahoo 获取实时股价 | `get_stock_price(code)` → `{current_price, change_percent, name, ...}` |
| **services/feishu_notifier** | 飞书机器人通知发送（告警/重买提醒/测试） | `send_alert(...)`, `send_rebuy_reminder(...)`, `send_test()` |
| **services/monitor** | 后台定时监控循环（daemon 线程） | `start_monitor()`, `stop_monitor()`, `check_and_notify(...)` |
| **routes/stock_api** | RESTful API（Blueprint） | 见下方接口清单 |
| **vue-project** | Vue 3 SPA 前端（替代旧模板） | Pinia + Composables + 组件化 |
| **app** | 页面渲染路由 + 应用启动 | `app.py` 启动 Flask，Vue 构建后集成 |

## API 接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | 获取所有正常股票（含实时价格） |
| POST | `/api/stocks` | 添加股票（`target_price_direction`不传时后端自动推断：目标价≥当前价→1，＜当前价→-1） |
| GET | `/api/stocks/deleted` | 获取所有已删除股票 |
| PUT | `/api/stocks/<code>` | 更新股票（含代码变更）；`target_price`变更且`target_price_direction`不传时自动推断方向 |
| DELETE | `/api/stocks/<code>` | 软删除（is_deleted=1） |
| POST | `/api/stocks/<code>/restore` | 恢复已删除股票 |
| DELETE | `/api/stocks/<code>/destroy` | 彻底删除（永久移除） |
| GET | `/api/stocks/check-code` | 检查代码格式及重复 |
| GET | `/api/interval` | 获取监控间隔 |
| PUT | `/api/interval` | 设置监控间隔 |
| GET | `/api/price/<code>` | 获取单只股票实时价格 |
| GET | `/api/stock-name/<code>` | 根据代码获取股票名称 |
| POST | `/api/test-notify` | 发送飞书测试通知 |
| POST | `/api/frontend-error` | 前端JS错误上报并记录 |

## 数据库表结构

### stocks

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | TEXT PK | 股票代码，如 601857 |
| `name` | TEXT | 股票名称 |
| `threshold_percent` | REAL | 触发通知涨跌幅阈值（正数=涨幅，负数=跌幅） |
| `target_price` | REAL | 目标价格（NULL=不启用） |
| `target_price_direction` | INTEGER | 1=止盈监控（涨破目标价触发），-1=买入监控（跌到目标价触发）；新增/修改时若前端未传则后端自动推断 |
| `monitor_enabled` | INTEGER | 0=暂停监控，1=启用监控 |
| `rebuy_enabled` | INTEGER | 0=关闭，1=启用重新买进提醒 |
| `rebuy_date` | TEXT | 重新买进提醒日期（YYYY-MM-DD） |
| `rebuy_time` | TEXT | 重新买进提醒时间（HH:MM:SS），默认 09:00:00 |
| `is_deleted` | INTEGER | 0=正常，1=已删除（软删除） |
| `deleted_at` | TEXT | 删除时间（ISO 格式） |
| `created_at` | TEXT | 创建时间 |
| `updated_at` | TEXT | 最后更新时间 |

### config

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | TEXT PK | 配置键名 |
| `value` | TEXT | 配置值 |

## 日志模块 (logs/)

| 文件 | 说明 |
|------|------|
| `logger.py` | 日志记录工具，提供 `log_api_error`, `log_api_info`, `log_stock_update`, `log_frontend_error` |
| `api_errors.log` | 后端API接口报错（网络、数据库、业务逻辑错误） |
| `frontend_errors.log` | 前端操作报错（JS捕获后上报后端记录） |
| `stock_updates.log` | 股票信息变更记录（代码变更、其他字段更新） |

## 日志格式
```
[时间] [级别] [来源] 消息
```

## Vue 前端架构

| 组件/文件 | 职责 |
|---------|------|
| `stockStore.js` | Pinia 状态：股票列表、已删除列表、间隔配置 |
| `useToast.js` | 页面级 Toast 通知 |
| `useModal.js` | 弹窗状态管理 |
| `stocks.js` | 封装所有 `/api/*` 调用 |
| `StockTable.vue` | 监控列表主表格，含实时价格、开关、CRUD |
| `DeletedTable.vue` | 回收站表格，含恢复/彻底删除 |
| `StockModal.vue` | 添加/编辑弹窗，含代码校验+自动获取名称 |
| `ConfirmModal.vue` | 软删除确认 |
| `DestroyModal.vue` | 彻底删除确认 |
| `IntervalBar.vue` | 全局监控频率设置 |
| `NavTabs.vue` | 导航标签页（含回收站计数 badge） |
| `ToastNotification.vue` | Toast 通知渲染 |
