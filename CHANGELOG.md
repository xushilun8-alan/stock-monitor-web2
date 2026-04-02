# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
