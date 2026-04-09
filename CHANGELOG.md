# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-04-09

### Added
- **全局重置当日股价告警通知** (`services/monitor.py`, `services/feishu_notifier.py`, `routes/stock_api.py`, `vue-project/`)
  - `POST /api/stocks/reset-all-alerts` 一键清空所有股票当日告警记录，实时生效无需重启
  - 双重清空：内存 `_notified_today` 集合 + `notification_status.json` 文件持久化
  - `MonitorLoop.get_monitor_instance()` 单例访问函数，统一实例来源
  - 前端 `IntervalBar.vue` 新增"重置告警"橙色按钮

### Fixed
- `clear_all_notifications()` 文件 key 匹配逻辑：`endswith(('_alert','_target'))` 改为 `'_alert_' in k or '_target_' in k`（key 以日期结尾，endswith 永远不匹配）
- `start_monitor()` 改为调用 `get_monitor_instance().start()`，解决单例分裂问题
- `reset_all_alerts()` 内存清空：`discard` 过滤改为 `clear()` 完全清空，避免遗漏
- `clear_all_notifications()` 新增清空全局 `_notified_today` 集合（feishu_notifier → monitor 的跨模块内存同步）

## [1.2.0] - 2026-04-08

### Added
- **涨跌幅阈值双值监控** (`models/`, `services/monitor.py`, `routes/stock_api.py`)
  - 支持同时配置上涨阈值（正数）和下跌阈值（负数），空格分隔，顺序不限（如 `5 -3`）
  - 独立判断：上涨触发上涨告警，下跌触发下跌告警，互不干扰
  - 告警 notif_key 拆分为 `_threshold_rise` / `_threshold_fall`，去重机制独立
  - 目标价告警 `_target` 保持独立，三类告警完全解耦
- **参数合法性校验** (`models/validate_threshold`)
  - 空值/单值（正/负）/双值（一正一负）→ 合规
  - 同号双值（如 `2 3`）、含非数字、超2个数值 → 保存时自动清空为 `""`（不监控）
  - 校验时机：仅在表单提交时执行，不影响运行时监控逻辑
- **`parse_threshold()` 解析函数** — 数据库存储字符串 → `(上涨阈值, 下跌阈值)`，兼容旧单值数据
- **`_fmt()` 格式化** — `5.0` 存储为 `"5"`，`2.5` 存储为 `"2.5"`，消除冗余小数位
- **`_attach_threshold()` 读取增强** — `get_monitor_stocks()` 等读取接口自动附加 `rise_threshold`/`fall_threshold` 字段
- **前端阈值输入升级** (`StockModal.vue`)
  - 输入框从 `type="number"` 改为 `type="text"`，支持空格输入双值
  - hint 文案说明三种合法格式（空/单值/双值一正一负）
- **阈值展示双行化** (`StockTable.vue`, `DeletedTable.vue`)
  - 双值：正数在上（绿色涨%），负数在下（红色跌%），分行显示
  - 空值显示"无"，单值正常显示

### Changed
- **数据库字段类型** — `threshold_percent` 从 `REAL` 迁移为 `TEXT`（支持双值存储）
- **`check_and_notify()` 参数** — `threshold_percent: float` 拆分为 `rise_threshold/fall_threshold: float|None`
- **`init_db()` 迁移逻辑** — 自动将旧 REAL 值转换为规范字符串存入新 TEXT 列

### Fixed
- `validate_threshold` 旧版 `"0 5"` 被错误判为合法（0 与正数组合不产生有效阈值），现已修复

### Tests
- `tests/test_threshold.py` — 覆盖校验/解析/告警逻辑共 18 项用例

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
