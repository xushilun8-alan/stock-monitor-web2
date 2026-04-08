#!/usr/bin/env python3
"""
数据库模型层 (models/__init__.py)

【核心功能】
- init_db(): 初始化 SQLite 表结构（stocks / config）
- 股票 CRUD: get_all_stocks, get_stock, add_stock, update_stock, delete_stock
- 软删除/恢复: delete_stock (is_deleted=1), restore_stock, permanent_delete_stock
- 监控配置: get_interval, set_interval, get_monitor_stocks
- 代码校验: is_code_exists

【数据库】
- 路径: data/stocks.db
- 表: stocks (code PK, name, threshold_percent, target_price,
               monitor_enabled, rebuy_enabled, rebuy_date, rebuy_time,
               is_deleted, deleted_at, created_at, updated_at)
         config (key PK, value)

【字段说明】
- is_deleted: 0=正常, 1=已删除（软删除）
- monitor_enabled: 0=暂停监控, 1=启用监控
- rebuy_enabled: 0=关闭提醒, 1=启用重新买进提醒
- threshold_percent: 触发通知的涨跌幅阈值（正数监控涨幅，负数监控跌幅）

【调用关系】
- 被 routes/stock_api.py (Flask API) 调用
- 被 services/monitor.py (后台监控) 调用
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stocks.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ─────────────────────────────────────────────────────────────
# 涨跌幅阈值解析与校验（供外部调用）
# ─────────────────────────────────────────────────────────────

def parse_threshold(threshold_str) -> tuple:
    """
    将数据库存储的 threshold_percent 字符串解析为 (上涨阈值, 下跌阈值)。

    存储格式（均为字符串）：
      ""          → (None, None)       不监控任何方向
      "5"         → (5.0, None)         仅监控涨幅
      "-3"        → (None, -3.0)        仅监控跌幅
      "5 -3"      → (5.0, -3.0)         同时监控涨跌幅

    Returns:
        tuple[float|None, float|None]: (上涨阈值, 下跌阈值)
    """
    if threshold_str is None:
        return (None, None)

    s = str(threshold_str).strip()
    if not s:
        return (None, None)

    try:
        # 单值情况（不带空格）
        if ' ' not in s:
            val = float(s)
            if val > 0:
                return (val, None)
            elif val < 0:
                return (None, val)
            else:
                return (None, None)  # 0 不监控任何方向

        # 双值情况（空格分隔，最多2个）
        parts = s.split()
        if len(parts) != 2:
            return (None, None)

        vals = [float(p) for p in parts]
        rise, fall = None, None
        for v in vals:
            if v > 0:
                rise = v
            elif v < 0:
                fall = v
        return (rise, fall)
    except (ValueError, TypeError):
        return (None, None)


def _fmt(val: float) -> str:
    """将数值规范化为字符串，整数不显示小数位（如 5.0 → '5'，5.5 → '5.5'）"""
    s = f"{val:.10g}"  # 采用最简方式，去除尾部多余的0
    return s


def validate_threshold(threshold_str) -> str:
    """
    校验并规范化用户输入的涨跌幅阈值字符串。

    合法的输入格式：
      ""（空）       → ""               不监控任何方向
      "5"            → "5"              单值正数（涨幅监控）
      "-3"           → "-3"             单值负数（跌幅监控）
      "5 -3"        → "5 -3"           双值一正一负（顺序不限）
      "-3 5"        → "5 -3"           双值自动规范排序（正数在前）
      " -3 5  "     → "5 -3"           去除首尾空白后规范化

    非法格式（返回空字符串，按不监控处理）：
      "2 3"  → 同正 → ""（同号双值不允许）
      "-4 -2" → 同负 → ""
      "5 a"  → 含非数字 → ""
      "3 -2 4" → 超过2个数值 → ""
      格式混乱 → ""

    Args:
        threshold_str: 用户输入的原始字符串

    Returns:
        str: 合规格式字符串（可直接写入数据库），非法时返回 ""
    """
    if threshold_str is None:
        return ""

    s = str(threshold_str).strip()
    if not s:
        return ""

    try:
        # 单值情况
        if ' ' not in s:
            val = float(s)
            if val == 0:
                return ""
            return _fmt(val)

        # 双值情况
        parts = s.split()
        if len(parts) != 2:
            return ""

        v1, v2 = float(parts[0]), float(parts[1])

        # 必须一正一负（0 分别与正/负组合时，0本身不产生阈值但另一值有效）
        # 判断：有一个严格正值 AND 有一个严格负值
        has_positive = v1 > 0 or v2 > 0
        has_negative = v1 < 0 or v2 < 0
        if not (has_positive and has_negative):
            return ""

        # 规范排序：正数在前，负数在后
        pos_val = v1 if v1 > 0 else v2
        neg_val = v1 if v1 < 0 else v2
        return f"{_fmt(pos_val)} {_fmt(neg_val)}"

    except (ValueError, TypeError):
        return ""


# 追踪当前连接，换路径前先关闭旧连接避免 SQLite file is locked
_conn = None


def _get_db():
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None
    _conn = sqlite3.connect(DB_PATH, timeout=10)
    _conn.row_factory = sqlite3.Row
    return _conn


def _close_db():
    """关闭当前连接（测试 fixture 清理用）"""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def init_db():
    """初始化数据库表结构（含字段迁移逻辑）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            threshold_percent TEXT DEFAULT '2.0',
            target_price REAL,
            target_price_direction INTEGER DEFAULT 1,
            monitor_enabled INTEGER DEFAULT 1,
            rebuy_enabled INTEGER DEFAULT 0,
            rebuy_date TEXT,
            rebuy_time TEXT DEFAULT '09:00:00',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    c.execute("INSERT OR IGNORE INTO config VALUES ('interval_seconds', '60')")
    # 字段迁移（已有数据不受影响）
    for col, typ in [('is_deleted', 'INTEGER DEFAULT 0'), ('deleted_at', 'TEXT'),
                      ('target_price_direction', 'INTEGER DEFAULT 1')]:
        try:
            c.execute(f"ALTER TABLE stocks ADD COLUMN {col} {typ}")
        except Exception:
            pass
    # 2026-04-08 迁移：threshold_percent 从 REAL → TEXT（支持双值存储）
    # SQLite 不支持 DROP COLUMN，用「追加新列+一次性转换」方式迁移
    try:
        # 检测旧 REAL 列是否仍存在（从未迁移过）
        col_info = c.execute("PRAGMA table_info(stocks)").fetchall()
        col_names = [r['name'] for r in col_info]
        has_real_old = 'threshold_percent' in col_names and \
                        any(r['type'] == 'REAL' for r in col_info if r['name'] == 'threshold_percent')
        if has_real_old:
            # 添加 TEXT 新列（若已存在则忽略）
            try:
                c.execute("ALTER TABLE stocks ADD COLUMN threshold_percent TEXT")
            except Exception:
                pass  # 列已存在
            # 把旧 REAL 值全部转为规范字符串存入新列
            rows = c.execute("SELECT code, threshold_percent FROM stocks").fetchall()
            for row in rows:
                old_val = row['threshold_percent']
                if old_val is not None:
                    # 转为字符串并规范化（正数直接，负数带负号）
                    str_val = str(float(old_val))
                    c.execute(
                        "UPDATE stocks SET threshold_percent = ? WHERE code = ?",
                        (str_val, row['code'])
                    )
    except Exception:
        pass
    conn.commit()
    conn.close()


def _attach_threshold(stock: dict) -> dict:
    """为股票记录附加 rise_threshold / fall_threshold 字段（供内部读取接口复用）"""
    rise, fall = parse_threshold(stock.get('threshold_percent'))
    stock['rise_threshold'] = rise
    stock['fall_threshold'] = fall
    return stock


def get_all_stocks(include_deleted: bool = False) -> List[Dict[str, Any]]:
    """
    获取股票列表
    - include_deleted=False (默认): 返回正常股票 (is_deleted=0)
    - include_deleted=True: 返回已删除股票 (is_deleted=1)，用于恢复管理
    """
    conn = _get_db()
    c = conn.cursor()
    if include_deleted:
        rows = c.execute(
            'SELECT * FROM stocks WHERE is_deleted = 1 ORDER BY deleted_at DESC'
        ).fetchall()
    else:
        rows = c.execute(
            'SELECT * FROM stocks WHERE is_deleted = 0 ORDER BY code'
        ).fetchall()
    conn.close()
    return [_attach_threshold(dict(r)) for r in rows]


def get_stock(code: str) -> Optional[Dict[str, Any]]:
    """根据代码获取单只股票（含已删除）"""
    conn = _get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM stocks WHERE code = ?', (code,)).fetchone()
    conn.close()
    return _attach_threshold(dict(row)) if row else None


def add_stock(code: str, name: str = '', threshold_percent='2.0',
              target_price: float = None, target_price_direction: int = 1,
              monitor_enabled: int = 1,
              rebuy_enabled: int = 0, rebuy_date: str = None,
              rebuy_time: str = '09:00:00') -> bool:
    """新增股票，返回 True 成功，False 失败（如代码已存在）

    Args:
        threshold_percent: 合规的阈值字符串（如 "2.0"、"5 -3"），保存前需经 validate_threshold() 校验
        target_price_direction: 1=止盈监控(涨破触发), -1=买入监控(跌到触发)
    """
    # 确保写入字符串（支持双值）
    th_str = str(threshold_percent) if threshold_percent is not None else '2.0'
    try:
        conn = _get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO stocks (code, name, threshold_percent, target_price,
                                target_price_direction, monitor_enabled, rebuy_enabled,
                                rebuy_date, rebuy_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code.upper(), name, th_str, target_price,
              target_price_direction, monitor_enabled, rebuy_enabled,
              rebuy_date, rebuy_time))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def update_stock(code: str, **kwargs) -> bool:
    """
    更新股票字段（仅允许白名单字段）
    白名单: name, threshold_percent, target_price, target_price_direction,
            monitor_enabled, rebuy_enabled, rebuy_date, rebuy_time
    """
    allowed = ['name', 'threshold_percent', 'target_price', 'target_price_direction',
               'monitor_enabled', 'rebuy_enabled', 'rebuy_date', 'rebuy_time']
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates['updated_at'] = datetime.now().isoformat()
    conn = _get_db()
    c = conn.cursor()
    set_clause = ', '.join([f"{k} = ?" for k in updates])
    values = list(updates.values()) + [code]
    c.execute(f'UPDATE stocks SET {set_clause} WHERE code = ?', values)
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    # 仅当告警相关字段变更时，才重置该股票的当日通知限制，允许重新触发
    # 其他字段（如 name、rebuy_time 等）变更不触发，避免误放行重复预警
    if ok:
        _alert_fields = {'threshold_percent', 'target_price', 'target_price_direction'}
        if set(updates.keys()) & _alert_fields:
            from services.feishu_notifier import reset_stock_notifications as _reset_stock_notif
            _reset_stock_notif(code)
    return ok


def delete_stock(code: str) -> bool:
    """
    软删除：将 is_deleted=1，保留数据
    仅对 is_deleted=0 的记录生效（防止重复删除）
    """
    conn = _get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        'UPDATE stocks SET is_deleted = 1, deleted_at = ? WHERE code = ? AND is_deleted = 0',
        (now, code)
    )
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def restore_stock(code: str) -> bool:
    """恢复已删除股票：重置为正常状态 (is_deleted=0)"""
    conn = _get_db()
    c = conn.cursor()
    c.execute(
        'UPDATE stocks SET is_deleted = 0, deleted_at = NULL WHERE code = ? AND is_deleted = 1',
        (code,)
    )
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def permanent_delete_stock(code: str) -> bool:
    """彻底删除：从数据库永久移除（仅限 is_deleted=1 的记录）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute('DELETE FROM stocks WHERE code = ? AND is_deleted = 1', (code,))
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def is_code_exists(code: str, exclude_code: str = '') -> bool:
    """
    检查股票代码是否已存在（排除自身，用于编辑时的重复检测）
    注意：仅检测 is_deleted=0 的正常股票
    """
    conn = _get_db()
    c = conn.cursor()
    if exclude_code:
        row = c.execute(
            'SELECT code FROM stocks WHERE code = ? AND code != ? AND is_deleted = 0',
            (code.upper(), exclude_code.upper())
        ).fetchone()
    else:
        row = c.execute(
            'SELECT code FROM stocks WHERE code = ? AND is_deleted = 0',
            (code.upper(),)
        ).fetchone()
    conn.close()
    return row is not None


def get_deleted_stocks() -> List[Dict[str, Any]]:
    """获取所有已删除股票（用于恢复管理页面）"""
    return get_all_stocks(include_deleted=True)


def get_monitor_stocks() -> List[Dict[str, Any]]:
    """获取启用监控的正常股票（支持重新买进提醒）"""
    conn = _get_db()
    c = conn.cursor()
    rows = c.execute(
        'SELECT * FROM stocks WHERE monitor_enabled = 1 AND is_deleted = 0 ORDER BY code'
    ).fetchall()
    conn.close()
    return [_attach_threshold(dict(r)) for r in rows]


def get_interval() -> int:
    """获取监控间隔（秒），默认 60"""
    conn = _get_db()
    c = conn.cursor()
    row = c.execute(
        "SELECT value FROM config WHERE key = 'interval_seconds'"
    ).fetchone()
    conn.close()
    return int(row['value']) if row else 60


def set_interval(seconds: int):
    """设置监控间隔（秒）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO config VALUES ('interval_seconds', ?)",
        (str(seconds),)
    )
    conn.commit()
    conn.close()


# 初始化数据库
init_db()
