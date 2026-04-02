# 股票监控系统 v2（Vue 3 SPA）

> 基于原 [stock-monitor-web](https://github.com/xushilun8-alan/stock-monitor-web) 重构，使用 Vue 3 + Pinia + Vite 构建专业股票监控界面。

## 技术栈

- **前端**: Vue 3 (Composition API + `<script setup>`) / Pinia / Vite
- **后端**: Flask + SQLite（与原版完全一致）
- **端口**: Vue Dev Server `5173` | Flask API `5188`

## 快速启动

```bash
# 方式一：一键启动（推荐）
./run.sh

# 方式二：分别启动
# 终端 1 — Flask 后端
python app.py

# 终端 2 — Vue 开发服务器
cd vue-project && npm install && npm run dev
```

访问 **http://localhost:5173**

## 功能清单

| 功能 | 状态 |
|------|------|
| 监控列表（含实时价格） | ✅ |
| 回收站管理（恢复/彻底删除） | ✅ |
| 添加股票（代码自动校验+名称获取） | ✅ |
| 编辑股票（含代码变更） | ✅ |
| 软删除 + 确认弹窗 | ✅ |
| 永久删除 + 确认弹窗 | ✅ |
| 监控开关（开/关） | ✅ |
| 全局监控频率设置 | ✅ |
| 测试飞书通知 | ✅ |
| 回收站计数 Badge | ✅ |
| Toast 操作反馈 | ✅ |
| 30 秒自动刷新价格 | ✅ |

## 生产构建

```bash
cd vue-project
npm install
npm run build
```

构建产物输出到 `vue-project/dist/`，Flask 在非 debug 模式下自动服务静态文件。

## API 端点（与原版一致）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | 获取监控列表（含实时价格） |
| POST | `/api/stocks` | 添加股票 |
| PUT | `/api/stocks/:code` | 更新股票 |
| DELETE | `/api/stocks/:code` | 软删除 |
| GET | `/api/stocks/deleted` | 获取已删除列表 |
| POST | `/api/stocks/:code/restore` | 恢复 |
| DELETE | `/api/stocks/:code/destroy` | 彻底删除 |
| GET | `/api/stocks/check-code?code=X` | 校验代码 |
| GET/PUT | `/api/interval` | 获取/设置监控频率 |
| GET | `/api/stock-name/:code` | 获取股票名称 |
| POST | `/api/test-notify` | 测试飞书通知 |

## 目录结构

```
stock-monitor-web2/
├── vue-project/          # Vue 3 SPA
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── api/stocks.js
│   │   ├── stores/stockStore.js
│   │   ├── composables/
│   │   └── components/
│   ├── vite.config.js    # /api 代理到 :5188
│   └── package.json
├── app.py                # Flask 主应用（服务 Vue build）
├── services/             # 股价数据/监控/飞书通知
├── models/               # 数据库模型
├── routes/               # API 路由
├── data/                 # SQLite DB + 配置
├── logs/                 # 日志
└── run.sh                # 启动脚本
```
