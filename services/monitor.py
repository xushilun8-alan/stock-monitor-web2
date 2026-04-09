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
from services.feishu_notifier import register_inmemory_reset_callback

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


def check_and_notify(code: str, name: str,
                     rise_threshold: float = None, fall_threshold: float = None,
                     target_price: float = None, target_price_direction: int = 1,
                     price_data: dict = None):
    """
    检查是否触发涨跌幅/目标价告警，发送飞书通知。

    2026-04-08 改：为支持双值阈值，参数由 threshold_percent 改为 rise_threshold/fall_threshold，
    由调用方（MonitorLoop._loop）通过 parse_threshold() 解析后传入。

    触发条件（各自独立判断，可同时触发）:
    1. rise_threshold 非 None 且 change_percent >= rise_threshold → 上涨告警
    2. fall_threshold 非 None 且 change_percent <= fall_threshold → 下跌告警
    3. target_price_direction == 1 and current_price >= target_price → 止盈监控
    4. target_price_direction == -1 and current_price <= target_price → 买入监控

    告警类型使用独立 notif_key（_threshold_rise / _threshold_fall / _target），
    相互独立，互不拦截。
    """
    global _notified_today

    if price_data is None:
        price_data = {}

    _reset_daily_cache()

    change_percent = price_data.get('change_percent', 0)
    current_price = price_data.get('current_price', 0)

    # ── 上涨告警（仅当配置了上涨阈值且涨幅达标）─────────────────
    rise_triggered = False
    rise_reason = ""
    if rise_threshold is not None and rise_threshold > 0:
        if change_percent >= rise_threshold:
            rise_triggered = True
            rise_reason = f"涨幅 {change_percent:+.2f}% 达上涨阈值 {rise_threshold}%"

    # ── 下跌告警（仅当配置了下跌阈值且跌幅达标）─────────────────
    fall_triggered = False
    fall_reason = ""
    if fall_threshold is not None and fall_threshold < 0:
        if change_percent <= fall_threshold:
            fall_triggered = True
            fall_reason = f"跌幅 {change_percent:+.2f}% 达下跌阈值 {abs(fall_threshold)}%"

    # 发送上涨告警
    if rise_triggered:
        notif_key = f"{code}_threshold_rise"
        if notif_key not in _notified_today:
            ok = send_alert(
                stock_code=code,
                stock_name=name or code,
                current_price=current_price,
                change_percent=change_percent,
                opening_price=price_data.get('opening_price', 0),
                high=price_data.get('high', 0),
                low=price_data.get('low', 0),
                reason=rise_reason,
            )
            if ok:
                _notified_today.add(notif_key)

    # 发送下跌告警（独立于上涨告警）
    if fall_triggered:
        notif_key = f"{code}_threshold_fall"
        if notif_key not in _notified_today:
            ok = send_alert(
                stock_code=code,
                stock_name=name or code,
                current_price=current_price,
                change_percent=change_percent,
                opening_price=price_data.get('opening_price', 0),
                high=price_data.get('high', 0),
                low=price_data.get('low', 0),
                reason=fall_reason,
            )
            if ok:
                _notified_today.add(notif_key)

    # ── 目标价告警（独立于涨跌幅告警）────────────────────────
    target_triggered = False
    target_reason = ""
    if target_price and target_price > 0:
        if target_price_direction == 1:
            if current_price >= target_price:
                target_triggered = True
                target_reason = f"股价 {current_price:.2f} 达到/突破目标价 {target_price:.2f}（止盈监控）"
        elif target_price_direction == -1:
            if current_price <= target_price:
                target_triggered = True
                target_reason = f"股价 {current_price:.2f} 跌至目标价 {target_price:.2f}（买入监控）"

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
            stocks = get_monitor_stocks()  # 返回数据已含 rise_threshold / fall_threshold
            if stocks:
                for stock in stocks:
                    price_data = get_stock_price(stock['code'])
                    if price_data:
                        check_and_notify(
                            code=stock['code'],
                            name=stock['name'],
                            rise_threshold=stock.get('rise_threshold'),
                            fall_threshold=stock.get('fall_threshold'),
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

    def reset_all_alerts(self):
        """
        全局重置：清空所有股票的当日股价告警通知记录（内存+文件）。
        不影响回购提醒、监控主循环、股价查询等原有功能。
        无参数、无返回值。
        """
        import logging
        logger = logging.getLogger(__name__)
        try:
            # 1. 完全清空全局内存告警去重集合
            global _notified_today
            count = len(_notified_today)
            _notified_today.clear()
            # 2. 清空文件持久化记录（feishu_notifier 内部也会清内存）
            from services.feishu_notifier import clear_all_notifications
            clear_all_notifications()
            logger.info(f"[Monitor] 全局重置股价告警完成，清除 {count} 条内存记录")
        except Exception as e:
            logger.error(f"[Monitor] 全局重置股价告警失败: {e}")


def _reset_inmemory_cache(stock_code: str):
    """重置指定股票在内存缓存中的通知记录（供 feishu_notifier 回调使用）"""
    global _notified_today
    keys_to_remove = [k for k in _notified_today if k.startswith(f"{stock_code}_")]
    for k in keys_to_remove:
        _notified_today.discard(k)


# 注册内存缓存重置回调
register_inmemory_reset_callback(_reset_inmemory_cache)

# 全局单例
_monitor = MonitorLoop()


def get_monitor_instance():
    """返回 MonitorLoop 系统单例，禁止新建实例"""
    return _monitor


def start_monitor():
    get_monitor_instance().start()


def stop_monitor():
    _monitor.stop()
