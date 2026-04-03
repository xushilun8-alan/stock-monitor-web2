# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-03

### Fixed
- **目标价方向自动判断逻辑修复** (`routes/stock_api.py`)
  - ADD 路径（新增股票）：`target_price >= 当前价 → 止盈(1)`，`target_price < 当前价 → 买入(-1)`；`current_price` 为空时默认止盈(1)
  - UPDATE 路径（修改股票）：同样逻辑，且修复了字符串与浮点数直接比较导致 TypeError 的问题（加 `float()` 强转）
  - 触发条件：前端**不发送** `target_price_direction` 字段时才自动判断；显式传入则使用传入值

## [1.0.0] - 2026-04-02

### Added
- **Vue 3 重构** — 前端从 Flask 模板（Jinja2 + Vanilla JS）迁移至 Vue 3 SPA
  - Composition API + `<script setup>`（无 TypeScript）
  - Vite 构建工具，Pinia 状态管理
  - Composables 封装：useToast、useModal
  - 组件化：StockTable、DeletedTable、StockModal、ConfirmModal、DestroyModal、IntervalBar、NavTabs、ToastNotification
  - 专业级深色主题 UI，贴合股票软件设计风格
- **Flask 后端完整保留** — API 接口不变，前端通过 Vite 代理访问
- **启动文件夹** — `启动/` 目录含启动/停止/查看状态脚本，双击即用
- **Git Hooks 自动记录** — 每次提交自动更新 MODULES.md 和 CHANGELOG.md
- **数据迁移** — SQLite 数据库和通知状态文件从原项目直接复用
