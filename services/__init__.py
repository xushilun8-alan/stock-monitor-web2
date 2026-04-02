"""
Services 服务包 (services/)

【子模块】
- services.stock_data: 股价数据获取（腾讯财经/新浪财经双数据源）
- services.feishu_notifier: 飞书通知发送（告警/重新买进提醒/测试）
- services.monitor: 后台监控调度（定时检查股票涨跌+重新买进）

【模块索引】
- get_stock_price(codes)  → services.stock_data
- send_alert(...)          → services.feishu_notifier
- MonitorLoop / start_monitor → services.monitor
"""

from services.stock_data import get_stock_price, batch_get_prices
from services.feishu_notifier import (
    send_alert, send_rebuy_reminder, send_test,
)
from services.monitor import start_monitor, stop_monitor

__all__ = [
    'get_stock_price', 'batch_get_prices',
    'send_alert', 'send_rebuy_reminder', 'send_test',
    'start_monitor', 'stop_monitor',
]
