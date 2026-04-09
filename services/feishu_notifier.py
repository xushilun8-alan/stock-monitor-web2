#!/usr/bin/env python3
"""
飞书通知服务 (services/feishu_notifier.py)

【核心功能】
- send_alert(): 股价达到涨跌幅阈值时发送飞书告警
- send_rebuy_reminder(): 发送重新买进提醒通知
- send_test(): 发送测试通知，验证连通性

【通知渠道】
- 通过飞书开放平台 API 直接调用
- 使用 Feishu Send Message API（receive_id 模式）
- 消息类型: text（纯文本）

【去重机制】
- 内存+文件双重检查：内存层（进程内 set） + 文件层（跨进程/跨日）
- 股票修改保存时触发 reset，清除该股票所有已通知状态
- reset 后首次触发放行（内存+文件均已清除），后续同日内正常拦截

【调用关系】
- 被 services/monitor.py (后台监控循环) 调用
- 无直接被 app.py 调用

【依赖】
- requests（已在 requirements.txt）
- json / os / fcntl / datetime（文件去重）
"""

import json
import os
import fcntl
import time
import requests
from datetime import datetime
from typing import Optional

from config import Config

# _notified_today 共享对象由 monitor.py 管理（避免循环导入，此模块不维护状态）


def _get_notified_today() -> set:
    """
    运行时从 monitor.py 获取共享的 _notified_today set。
    不缓存，每次实时访问以确保拿到正确的对象引用。
    """
    import sys
    try:
        _m = sys.modules.get('services.monitor')
        if _m is not None:
            return _m._notified_today
    except Exception:
        pass
    return set()

# ─── Feishu API 配置 ─────────────────────────────────────────
_FEISHU_APP_ID = Config.FEISHU_APP_ID
_FEISHU_APP_SECRET = Config.FEISHU_APP_SECRET
_FEISHU_RECEIVE_ID = Config.FEISHU_RECEIVE_ID
_FEISHU_RECEIVE_ID_TYPE = Config.FEISHU_RECEIVE_ID_TYPE

_API_BASE = "https://open.feishu.cn/open-apis"
_TOKEN_URL = f"{_API_BASE}/auth/v3/tenant_access_token/internal"
_MSG_URL = f"{_API_BASE}/im/v1/messages?receive_id_type={_FEISHU_RECEIVE_ID_TYPE}"

# ─── Token 缓存（进程内单例，避免频繁刷新） ────────────────────
_token_info = {"token": None, "expires_at": 0}


def _get_tenant_token() -> Optional[str]:
    """获取 tenant_access_token，带进程内缓存（有效期 2 小时）"""
    now = time.time()
    if _token_info["token"] and now < _token_info["expires_at"] - 60:
        return _token_info["token"]

    try:
        resp = requests.post(
            _TOKEN_URL,
            json={"app_id": _FEISHU_APP_ID, "app_secret": _FEISHU_APP_SECRET},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            _token_info["token"] = data["tenant_access_token"]
            _token_info["expires_at"] = now + data.get("expire", 7200)
            return _token_info["token"]
    except Exception as e:
        print(f"[Feishu] 获取 tenant_access_token 失败: {e}")
    return None


def _send_feishu_message(text: str) -> bool:
    """
    通过飞书开放平台 API 发送文本消息。
    返回 True = 发送成功，False = 失败。
    """
    token = _get_tenant_token()
    if not token:
        return False

    try:
        resp = requests.post(
            _MSG_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": _FEISHU_RECEIVE_ID,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
            timeout=15,
        )
        # code==0 表示成功
        return resp.json().get("code") == 0
    except Exception as e:
        print(f"[Feishu] 发送消息异常: {e}")
        return False


# ─── 文件去重逻辑（保持原接口不变） ─────────────────────────────
_NOTIF_LOCK_FILE = "data/.notif.lock"


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
    # 同步写内存，避免本次已发送的消息在内存层未记录
    mem_key = f"{stock_code}_{notif_type}"
    notified_today = _get_notified_today()
    notified_today.add(mem_key)
    return _set_notified(stock_code, notif_type, datetime.now().strftime('%Y-%m-%d'), notif_file)


def clear_rebuy_notification(stock_code: str, date: str,
                             notif_file: str = "data/notification_status.json"):
    """清除指定股票指定日期的 rebuy 通知记录"""
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


def clear_all_notifications(notif_file: str = "data/notification_status.json"):
    """
    清空所有股价告警通知的持久化记录。
    双重清空：内存集合（全局 _notified_today）+ 文件持久化。
    重置后下一轮监控满足条件即重新触发。
    无参数、无返回值。
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        # 1. 清空全局 _notified_today 中的所有告警 key（alert/target/rebuy）
        import sys
        _m = sys.modules.get('services.monitor')
        if _m is not None:
            notified = getattr(_m, '_notified_today', None)
            if notified:
                # 仅清除告警相关 key，保留其他类型
                keys_to_clear = [k for k in notified
                               if '_alert_' in k or '_target_' in k or '_rebuy_' in k]
                for k in keys_to_clear:
                    notified.discard(k)
                logger.info(f"[Feishu] 已清空内存集合中的 {len(keys_to_clear)} 条告警记录")
    except Exception as e:
        logger.error(f"[Feishu] 清空内存通知集合失败: {e}")

    # 2. 删除文件持久化记录
    try:
        if not os.path.exists(notif_file):
            logger.info("[Feishu] 告警通知文件不存在，无需删除")
            return
        os.remove(notif_file)
        logger.info("[Feishu] 告警通知文件已删除")
    except Exception as e:
        logger.error(f"[Feishu] 删除通知文件失败: {e}")


# ─── 对外接口 ─────────────────────────────────────────────────

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
    # 根据 reason 区分告警类型，使用独立 notif_type 避免相互拦截
    notif_type = 'target' if '目标价' in reason else 'alert'

    # 双重检查：
    # 1. 内存 key 检查（当日已发过则跳过）
    mem_key = f"{stock_code}_{notif_type}"
    notified_today = _get_notified_today()
    if mem_key in notified_today:
        return False  # 内存中已存在，当日不重复发送

    # 2. 文件 key 检查（跨进程/跨日去重）
    if _check_notified_today(stock_code, notif_type):
        return False  # 文件中已存在，当日不重复发送

    direction = "上涨" if change_percent > 0 else "下跌"
    message = f"""🚨【股价提醒】
股票：{stock_name} ({stock_code.upper()})
当前价：{current_price:.2f}元
{direction}：{change_percent:+.2f}%
原因：{reason}
时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    if _send_feishu_message(message):
        _set_notified_today(stock_code, notif_type)
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

    return _send_feishu_message(message)


def send_test() -> bool:
    """测试通知——发送测试消息验证飞书连通性"""
    message = f"""✅【监控系统测试】
时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
股票监控系统Web版，飞书通知功能正常！"""

    return _send_feishu_message(message)


# ─── 通知重置机制（股票修改时自动解除每日限制） ─────────────────────

# 内存缓存重置回调，由 monitor.py 注册
_inmemory_reset_cb = None


def register_inmemory_reset_callback(cb):
    """注册内存缓存重置回调（由 monitor.py 调用）"""
    global _inmemory_reset_cb
    _inmemory_reset_cb = cb


def reset_stock_notifications(stock_code: str,
                             notif_file: str = "data/notification_status.json"):
    """
    重置指定股票的当日通知状态，解除每日只发1次的限制。
    - 清除文件中的所有相关记录（alert / target / rebuy 所有类型，所有日期）
    - 触发内存缓存重置回调（清除普通通知 key）
    重置后，send_alert 依赖内存+文件双重检查放行，不依赖单次快速通道。
    """
    # 1. 清除文件中的记录（alert / target / rebuy 所有类型，所有日期）
    if not os.path.exists(notif_file):
        pass
    else:
        try:
            with open(notif_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 清除所有以该股票代码开头的 key（alert/target/rebuy 全部清除）
            keys_to_delete = [k for k in data if k.startswith(f"{stock_code}_")]
            for k in keys_to_delete:
                del data[k]
            with open(notif_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 2. 触发内存缓存重置（清除普通通知 key）
    if _inmemory_reset_cb:
        try:
            _inmemory_reset_cb(stock_code)
        except Exception:
            pass
