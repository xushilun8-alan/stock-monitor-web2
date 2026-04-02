#!/usr/bin/env python3
"""
后台监控调度服务 (services/monitor.py)

【核心功能】
- MonitorLoop: 后台线程循环，定时检查所有监控股票
- check_and_notify(): 检查单只股票是否触发涨跌幅/目标价告警
- check_rebuy_reminders(): 检查重新买进提醒是否到期

【监控逻辑】
1. 从 models.get_monitor_stocks() 获取当前监控列表
2. 调用 stock_data.get_stock_price() 获取最新价格
3. check_and_notify() 判断是否触发:
   - abs(change_percent) >= threshold_percent → 发送飞书告警
   - current_price >= target_price → 发送目标价到达告警
4. check_rebuy_reminders() 判断重新买进时间是否到期

【去重机制】
- 内存缓存 _notified_today: set，键=股票代码，值=当日已通知
- 每日凌晨自动重置（按日期判断）
- 仅针对涨跌幅告警，去重键=股票代码
- 重新买进提醒去重键=股票代码_时间点

【调用关系】
- 被 app.py 的 start_monitor() 在 Flask 启动时调用
- 调用 models.get_monitor_stocks / get_deleted_stocks / get_interval
- 调用 services.stock_data.get_stock_price
- 调用 services.feishu_notifier.send_alert / send_rebuy_reminder

【线程安全】
- MonitorLoop 使用 daemon 线程，可通过 stop_monitor() 安全停止
- 全局单例 _monitor，避免重复启动
"""

import os
import sys
import time
import threading
from datetime import datetime

# 兼容旧路径导入（monitor.py 曾位于根目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.stock_data import get_stock_price
from models import get_monitor_stocks, get_deleted_stocks, get_interval, update_stock
from services.feishu_notifier import clear_rebuy_notification, _try_mark_notified
from services.feishu_notifier import send_alert, send_rebuy_reminder

# 飞书通知去重：当日已通知过的股票代码集合（内存缓存）
_notified_today: set = set()
_last_notif_date: str = ""


def _reset_daily_cache():
    """每日凌晨重置通知缓存"""
    global _notified_today, _last_notif_date
    today = datetime.now().strftime('%Y-%m-%d')
    if today != _last_notif_date:
        _notified_today = set()
        _last_notif_date = today


def check_and_notify(code: str, name: str, threshold_percent: float,
                     target_price: float, target_price_direction: int = 1,
                     price_data: dict = None):
    """
    检查是否触发告警，发送飞书通知

    触发条件（各自独立判断，可同时触发）:
    1. abs(change_percent) >= threshold_percent → 涨跌告警
    2. target_price_direction == 1 and current_price >= target_price → 止盈监控
    3. target_price_direction == -1 and current_price <= target_price → 买入监控

    告警类型使用独立key，避免相互拦截。
    """
    global _notified_today

    if price_data is None:
        price_data = {}

    _reset_daily_cache()

    change_percent = price_data.get('change_percent', 0)
    current_price = price_data.get('current_price', 0)

    # 分别判断涨跌告警和目标价告警，独立发送
    # 涨跌告警 (threshold)
    threshold_triggered = False
    threshold_reason = ""
    if threshold_percent > 0:
        if change_percent >= threshold_percent:
            threshold_triggered = True
            threshold_reason = f"涨幅 {change_percent:+.2f}% 达阈值 {threshold_percent}%"
    elif threshold_percent < 0:
        if change_percent <= threshold_percent:
            threshold_triggered = True
            threshold_reason = f"跌幅 {change_percent:+.2f}% 达阈值 {abs(threshold_percent)}%"

    # 目标价告警 (target_price)，使用独立key和显式方向
    target_triggered = False
    target_reason = ""
    if target_price and target_price > 0:
        if target_price_direction == 1:
            # 止盈监控：涨破触发
            if current_price >= target_price:
                target_triggered = True
                target_reason = f"股价 {current_price:.2f} 达到/突破目标价 {target_price:.2f}（止盈监控）"
        elif target_price_direction == -1:
            # 买入监控：跌到触发
            if current_price <= target_price:
                target_triggered = True
                target_reason = f"股价 {current_price:.2f} 跌至目标价 {target_price:.2f}（买入监控）"

    # 发送涨跌告警
    if threshold_triggered:
        notif_key = f"{code}_threshold"
        if notif_key not in _notified_today:
            ok = send_alert(
                stock_code=code,
                stock_name=name or code,
                current_price=current_price,
                change_percent=change_percent,
                opening_price=price_data.get('opening_price', 0),
                high=price_data.get('high', 0),
                low=price_data.get('low', 0),
                reason=threshold_reason,
            )
            if ok:
                _notified_today.add(notif_key)

    # 发送目标价告警（独立于涨跌告警）
    if target_triggered:
        notif_key = f"{code}_target"
        if notif_key not in _notified_today:
            ok = send_alert(
                stock_code=code,
                stock_name=name or code,
                current_price=current_price,
                change_percent=change_percent,
                opening_price=price_data.get('opening_price', 0),
                high=price_data.get('high', 0),
                low=price_data.get('low', 0),
                reason=target_reason,
            )
            if ok:
                _notified_today.add(notif_key)
                # 触发后自动清除目标价，避免重复提醒
                update_stock(code, target_price=None, target_price_direction=1)


def check_rebuy_reminders():
    """
    检查重新买进提醒
    - 同时查询「正常股票」和「已删除但开启提醒的股票」
    - 精确到秒：只有当前时间 >= 提醒时间才触发
    - 去重键包含时间点，同日多个时间点不会重复通知
    """
    global _notified_today

    _reset_daily_cache()

    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    current_time_str = now.strftime('%H:%M:%S')

    active = get_monitor_stocks()
    deleted = get_deleted_stocks()
    all_rebuy = active + [s for s in deleted if s.get('rebuy_enabled') and s.get('rebuy_date')]

    for stock in all_rebuy:
        if not stock.get('rebuy_enabled') or not stock.get('rebuy_date'):
            continue
        if stock['rebuy_date'] != today_str:
            continue

        rebuy_time = stock.get('rebuy_time') or '09:00:00'
        if current_time_str < rebuy_time:
            continue

        code = stock['code']
        notif_key = f"{code}_rebuy_{rebuy_time}"
        if notif_key in _notified_today:
            continue

        try:
            price_data = get_stock_price(code)
        except Exception as e:
            import logging
            logging.error(f"[REBUY] get_stock_price({code}) failed: {e}")
            price_data = None
        if not price_data:
            continue

        # 原子化 check+mark（单次锁获取）：获得发送权才发
        if not _try_mark_notified(code, 'rebuy', stock['rebuy_date']):
            continue  # 其他进程已获得发送权，跳过

        try:
            ok = send_rebuy_reminder(
                stock_code=code,
                stock_name=stock['name'] or code,
                remind_date=stock['rebuy_date'],
                remind_time=rebuy_time,
                current_price=price_data['current_price'],
                change_percent=price_data['change_percent'],
            )
        except Exception as e:
            import logging
            logging.error(f"[REBUY] send_rebuy_reminder({code}) failed: {e}")
            ok = False
        if ok:
            _notified_today.add(notif_key)
            # 自动清除 rebuy 时间，避免重复触发
            update_stock(code, rebuy_enabled=0, rebuy_date=None, rebuy_time='09:00:00')
            clear_rebuy_notification(code, stock['rebuy_date'])


class MonitorLoop:
    """后台监控循环，可动态启停"""

    def __init__(self):
        self._running = False
        self._thread: threading.Thread = None

    def _loop(self):
        while self._running:
            interval = get_interval()
            stocks = get_monitor_stocks()
            if stocks:
                for stock in stocks:
                    price_data = get_stock_price(stock['code'])
                    if price_data:
                        check_and_notify(
                            code=stock['code'],
                            name=stock['name'],
                            threshold_percent=stock['threshold_percent'],
                            target_price=stock.get('target_price'),
                            target_price_direction=stock.get('target_price_direction', 1),
                            price_data=price_data,
                        )
            # rebuy 提醒检查独立于股票列表，避免无股票时漏检
            check_rebuy_reminders()
            time.sleep(interval)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)


# 全局单例
_monitor = MonitorLoop()


def start_monitor():
    _monitor.start()


def stop_monitor():
    _monitor.stop()
