#!/usr/bin/env python3
"""
飞书通知服务 (services/feishu_notifier.py)

【核心功能】
- send_alert(): 股价达到涨跌幅阈值时发送飞书告警
- send_rebuy_reminder(): 发送重新买进提醒通知
- send_test(): 发送测试通知，验证连通性

【通知渠道】
- 通过 openclaw message send --channel feishu 发送
- 飞书机器人目标 ID: ou_268fcd21ee877df7e4d16305a4892d7c

【涨跌幅提醒逻辑】
- change_percent > 0 → 上涨，提醒文本显示「上涨 X%」
- change_percent < 0 → 下跌，提醒文本显示「下跌 X%」
- abs(change_percent) >= threshold → 触发通知

【去重机制】
- 使用 data/notification_status.json 记录当日已通知股票
- 每个交易日自动重置缓存

【调用关系】
- 被 services/monitor.py (后台监控循环) 调用
- 无直接被 app.py 调用

【依赖】
- subprocess (调用 openclaw CLI)
- json / os / datetime (文件去重)

【配置】
- FEISHU_TARGET: 飞书机器人 WebHook 或 Bot ID
"""

import subprocess
import json
import os
import fcntl
from datetime import datetime
from typing import Optional

FEISHU_TARGET = "ou_268fcd21ee877df7e4d16305a4892d7c"
_NOTIF_LOCK_FILE = "data/.notif.lock"


def _call_openclaw(cmd: list) -> bool:
    """通过 openclaw CLI 发送消息，返回是否成功"""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result.returncode == 0


def _notification_key(stock_code: str, notif_type: str, date: str) -> str:
    return f"{stock_code}_{notif_type}_{date}"


def _try_mark_notified(stock_code: str, notif_type: str, date: str,
                       notif_file: str = "data/notification_status.json") -> bool:
    """
    原子化 check+mark：持有锁期间检查并写入。
    返回 True = 标记成功（之前未标记，本进程获得发送权）
    返回 False = 已标记（其他进程已获得发送权，本进程跳过）
    """
    key = _notification_key(stock_code, notif_type, date)
    lock_path = _NOTIF_LOCK_FILE
    os.makedirs(os.path.dirname(notif_file), exist_ok=True)

    try:
        with open(lock_path, 'a') as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                data = {}
                if os.path.exists(notif_file):
                    with open(notif_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                if data.get(key):
                    return False  # 已标记，跳过
                data[key] = True
                with open(notif_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
    except Exception:
        return False


# 保留旧接口以兼容，但内部委托给 _try_mark_notified
def _check_notified(stock_code: str, notif_type: str, date: str,
                    notif_file: str = "data/notification_status.json") -> bool:
    """检查指定股票在指定日期指定类型是否已通知（文件锁保护）"""
    return not _try_mark_notified(stock_code, notif_type, date, notif_file)


def _set_notified(stock_code: str, notif_type: str, date: str,
                  notif_file: str = "data/notification_status.json"):
    """标记指定股票在指定日期指定类型已通知（文件锁保护）"""
    _try_mark_notified(stock_code, notif_type, date, notif_file)


def _check_notified_today(stock_code: str, notif_type: str = 'alert',
                          notif_file: str = "data/notification_status.json") -> bool:
    """兼容旧接口，默认用今日日期"""
    return _check_notified(stock_code, notif_type, datetime.now().strftime('%Y-%m-%d'), notif_file)


def _set_notified_today(stock_code: str, notif_type: str = 'alert',
                        notif_file: str = "data/notification_status.json"):
    """兼容旧接口，默认用今日日期"""
    return _set_notified(stock_code, notif_type, datetime.now().strftime('%Y-%m-%d'), notif_file)


def clear_rebuy_notification(stock_code: str, date: str,
                             notif_file: str = "data/notification_status.json"):
    """清除指定股票指定日期的 rebuy 通知记录（支持同股同日多时间点场景）"""
    key = _notification_key(stock_code, 'rebuy', date)
    if not os.path.exists(notif_file):
        return
    try:
        with open(notif_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if key in data:
            del data[key]
            with open(notif_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def send_alert(stock_code: str, stock_name: str, current_price: float,
               change_percent: float, opening_price: float,
               high: float, low: float,
               reason: str = "涨幅超限") -> bool:
    """
    发送股价告警飞书通知

    参数:
        stock_code: 股票代码 (如 601857)
        stock_name: 股票名称
        current_price: 当前价格
        change_percent: 涨跌幅百分比 (正=涨, 负=跌)
        opening_price: 开盘价
        high / low: 最高/最低价
        reason: 触发原因描述

    返回:
        True = 发送成功，False = 今日已通知或发送失败
    """
    if _check_notified_today(stock_code, 'alert'):
        return False  # 今天已通知过

    direction = "上涨" if change_percent > 0 else "下跌"
    message = f"""🚨【股价提醒】
股票：{stock_name} ({stock_code.upper()})
当前价：{current_price:.2f}元
{direction}：{change_percent:+.2f}%
原因：{reason}
时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'feishu',
        '--target', FEISHU_TARGET,
        '--message', message
    ]

    if _call_openclaw(cmd):
        _set_notified_today(stock_code, 'alert')
        return True
    return False


def send_rebuy_reminder(stock_code: str, stock_name: str,
                        remind_date: str, remind_time: str,
                        current_price: float,
                        change_percent: float) -> bool:
    """
    发送重新买进提醒（发送前须已在 monitor.py 端完成文件标记）。
    函数内部不再读写文件，避免与 monitor.py 端的标记操作产生竞态。
    """
    message = f"""📣【重新买进提醒】
股票：{stock_name} ({stock_code.upper()})
提醒日期：{remind_date}
提醒时间：{remind_time}
当前价：{current_price:.2f}元
今日涨幅：{change_percent:+.2f}%
时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ 到达设定的重新买进时间，请关注！"""

    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'feishu',
        '--target', FEISHU_TARGET,
        '--message', message
    ]

    return _call_openclaw(cmd)


def send_test() -> bool:
    """测试通知——发送测试消息验证飞书连通性"""
    message = f"""✅【监控系统测试】
时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
股票监控系统Web版，飞书通知功能正常！"""

    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'feishu',
        '--target', FEISHU_TARGET,
        '--message', message
    ]
    return _call_openclaw(cmd)
