# stage_buying 模块文档

## 目录结构

```
stage_buying/
├── __init__.py          # 蓝图注册
├── models.py            # SQLite 数据库模型
├── routes.py            # Flask Blueprint API 路由
├── service.py           # 核心业务逻辑
├── utils.py             # 飞书通知 + Excel 导入导出
├── CHANGELOG.md         # 本模块变更记录
└── MODULES.md            # 本模块文档
```

## 模块职责

分阶段买入策略管理模块。根据用户设定的初始股价、初始股数、每阶段追加股数、幅度系数等参数，自动计算 N 个买入阶段（默认 9 阶段），支持实时价格监控触发、飞书通知推送、Excel 批量导入导出。

## 核心算法

`service.py::calculate_stages(params)` — 多阶段买入计划计算：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `initial_price` | 初始单价（必填） | — |
| `initial_shares` | 阶段1股数（必填） | — |
| `per_stage_shares` | 每阶段追加股数（必填） | — |
| `stage_count` | 总阶段数 | 9 |
| `serial_coefficient` | 序号系数 | 1.0 |
| `amplitude_coefficient` | 幅度系数 | 0.08 |
| `decline_coefficient` | 跌幅系数 | 0.975 |
| `amplitude_multiplier` | 幅度乘数 | 1.001 |
| `floor_price` | 底价（可 null） | null |
| `target_price` | 目标价（可 null） | null |

**阶段 1**：`amplitude=1.0`，`buy_price=initial_price`，`shares=initial_shares`
**阶段 2**：`amplitude = decline_coefficient × (serial_coefficient - 0.1 + amplitude_coefficient)`
**阶段 3+**：`amplitude = prev_amplitude × amplitude_multiplier^(n-2)`

每阶段产出：`{ stage_number, amplitude, buy_price, shares, buy_amount, floor_loss, loss_rate, target_income, expected_return, return_rate, status }`

## 数据库表结构

### stage_stocks（主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `code` | TEXT UNIQUE | 股票代码 |
| `name` | TEXT | 股票名称 |
| `initial_price` | REAL | 初始单价 |
| `initial_shares` | INTEGER | 阶段1股数 |
| `per_stage_shares` | INTEGER | 每阶段追加股数 |
| `stage_count` | INTEGER | 总阶段数，默认 9 |
| `serial_coefficient` | REAL | 序号系数 |
| `amplitude_coefficient` | REAL | 幅度系数 |
| `decline_coefficient` | REAL | 跌幅系数 |
| `target_price` | REAL | 目标价 |
| `min_amplitude` | REAL | 最小幅度 |
| `amplitude_multiplier` | REAL | 幅度乘数 |
| `floor_price` | REAL | 底价 |
| `created_at` | TEXT | 创建时间 |
| `updated_at` | TEXT | 更新时间 |

### stage_details（阶段详情表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `stock_id` | INTEGER FK | 关联 stage_stocks.id |
| `stage_number` | INTEGER | 阶段编号（1~N） |
| `amplitude` | REAL | 幅度 |
| `buy_price` | REAL | 买入单价 |
| `shares` | INTEGER | 买入股数 |
| `buy_amount` | REAL | 买入金额 |
| `floor_loss` | REAL | floor loss |
| `loss_rate` | REAL | 亏损率 |
| `target_income` | REAL | 目标收益 |
| `expected_return` | REAL | 预期收益 |
| `return_rate` | REAL | 收益率 |
| `status` | TEXT | 触发状态：`untriggered` / `triggered` |

### trigger_records（触发记录表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `stock_id` | INTEGER FK | 关联 stage_stocks.id |
| `stage_id` | INTEGER FK | 关联 stage_details.id |
| `trigger_price` | REAL | 触发时价格 |
| `trigger_time` | TEXT | 触发时间 |

### config（配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | TEXT PK | 配置键名 |
| `value` | TEXT | 配置值 |

## API 接口清单（stage_buying_bp）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stage-buying/stocks` | 获取所有阶段股票（含实时价格） |
| POST | `/api/stage-buying/stocks` | 新增股票（含自动建阶段） |
| GET | `/api/stage-buying/stocks/<id>` | 获取单个股票及阶段详情 |
| PUT | `/api/stage-buying/stocks/<id>` | 更新股票（含重新计算阶段） |
| DELETE | `/api/stage-buying/stocks/<id>` | 删除股票（软删除） |
| POST | `/api/stage-buying/stocks/calculate` | 仅计算阶段（不保存） |
| GET | `/api/stage-buying/stocks/<id>/summary` | 获取阶段汇总（触发进度） |
| POST | `/api/stage-buying/stocks/<id>/toggle/<stage_id>` | 切换阶段执行状态 |
| POST | `/api/stage-buying/stocks/<id>/trigger` | 手动触发检查（模拟） |
| GET | `/api/stage-buying/trigger-records` | 查询触发记录 |
| GET | `/api/stage-buying/config/<key>` | 获取配置项 |
| PUT | `/api/stage-buying/config/<key>` | 更新配置项 |
| POST | `/api/stage-buying/import` | Excel 导入阶段计划 |
| GET | `/api/stage-buying/export/<stock_id>` | 导出单只股票阶段计划为 Excel |

## 触发通知机制

后台监控线程 `_stage_monitor_loop()` 每 60 秒执行一次：
1. 遍历所有阶段股票，获取实时价格
2. 调用 `check_and_trigger_stages(stock_id)` 检查是否有阶段触发
3. 触发条件：`current_price <= stage.buy_price`
4. 已触发阶段通过 `data/stage_notif_status.json` 去重，防止重复通知
5. 发送飞书消息至 `FEISHU_TARGET`（见 `utils.py::send_stage_trigger_notification`）

## Vue 前端视图

路径：`vue-project/src/views/StageBuying/`

| 文件 | 职责 |
|------|------|
| `index.vue` | 主视图容器 |
| `store.js` | Pinia 状态管理 |
| `api.js` | API 客户端封装 |
| `components/StockForm.vue` | 股票表单（新增/编辑） |
| `components/StageTable.vue` | 阶段详情表格 |
| `components/Charts.vue` | 价格/阶段可视化图表 |
| `components/TriggerRecord.vue` | 触发记录查询 |
