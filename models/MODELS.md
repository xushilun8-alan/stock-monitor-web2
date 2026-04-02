# Models 模块文档 (models/)

## 核心职责
封装 SQLite 数据库操作，提供股票数据的持久化 CRUD 接口。

## init_db()
初始化 stocks / config 表，并自动执行字段迁移（兼容旧数据库）。

## 函数清单

| 函数 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `get_all_stocks(include_deleted)` | `include_deleted=False` | `List[Dict]` | 获取股票列表 |
| `get_stock(code)` | code: str | `Dict\|None` | 获取单只股票 |
| `add_stock(...)` | code, name, threshold_percent, target_price, monitor_enabled, rebuy_enabled, rebuy_date, rebuy_time | `bool` | 新增 |
| `update_stock(code, **kwargs)` | 白名单字段 | `bool` | 更新 |
| `delete_stock(code)` | code | `bool` | 软删除 (is_deleted=1) |
| `restore_stock(code)` | code | `bool` | 恢复 (is_deleted=0) |
| `permanent_delete_stock(code)` | code | `bool` | 彻底删除 |
| `is_code_exists(code, exclude_code)` | code, exclude_code='' | `bool` | 代码重复检测 |
| `get_deleted_stocks()` | — | `List[Dict]` | 获取已删除股票 |
| `get_monitor_stocks()` | — | `List[Dict]` | 获取启用监控的正常股票 |
| `get_interval()` | — | `int` | 获取监控间隔（秒） |
| `set_interval(seconds)` | int | — | 设置监控间隔 |

## update_stock 白名单字段
`name`, `threshold_percent`, `target_price`, `monitor_enabled`, `rebuy_enabled`, `rebuy_date`, `rebuy_time`

（传入其他字段将被静默忽略）

## 与其他模块的关系
- **routes/stock_api.py**: 所有 API 路由调用 models 层
- **services/monitor.py**: 调用 `get_monitor_stocks()`, `get_deleted_stocks()`, `get_interval()`
