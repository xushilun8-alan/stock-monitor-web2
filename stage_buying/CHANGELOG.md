# Changelog — stage_buying 模块

All notable changes to the `stage_buying` module will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] - 2026-04-04

### Added

- **阶段买入核心模块** — 从零构建完整分阶段买入策略管理模块
  - `models.py` — SQLite 数据库模型：stage_stocks（主表）、stage_details（阶段详情表）、trigger_records（触发记录表）、config（配置表）
  - `routes.py` — Flask Blueprint，完整 RESTful API（CRUD + 阶段计算 + 触发 + 导入导出）
  - `service.py` — 核心业务逻辑：calculate_stages 算法、create_stock_with_stages、check_and_trigger_stages、刷新价格等
  - `utils.py` — 飞书通知发送、Excel 导入/导出
- **多阶段买入算法** — 支持自定义阶段数、幅度系数、跌幅系数、序号系数、底价等参数
- **飞书机器人通知** — 阶段触发时自动推送带图表消息（股票名、当前价、买入价、股数、触发时间）
- **Excel 导入/导出** — 支持从 Excel 批量导入阶段计划、导出已有计划
- **后台价格监控线程** — 每 60 秒遍历所有阶段股票，检查是否触发并推送通知
- **触发去重** — 基于 `data/stage_notif_status.json` 防止重复通知
- **Vue 前端视图** — `vue-project/src/views/StageBuying/` 含表单、表格、图表、触发记录组件
- **模块注册** — `app.py` 中注册 `stage_buying_bp` Blueprint
