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


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构（含字段迁移逻辑）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            threshold_percent REAL DEFAULT 2.0,
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
    conn.commit()
    conn.close()


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
    return [dict(r) for r in rows]


def get_stock(code: str) -> Optional[Dict[str, Any]]:
    """根据代码获取单只股票（含已删除）"""
    conn = _get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM stocks WHERE code = ?', (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_stock(code: str, name: str = '', threshold_percent: float = 2.0,
              target_price: float = None, target_price_direction: int = 1,
              monitor_enabled: int = 1,
              rebuy_enabled: int = 0, rebuy_date: str = None,
              rebuy_time: str = '09:00:00') -> bool:
    """新增股票，返回 True 成功，False 失败（如代码已存在）
    
    Args:
        target_price_direction: 1=止盈监控(涨破触发), -1=买入监控(跌到触发)
    """
    try:
        conn = _get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO stocks (code, name, threshold_percent, target_price,
                                target_price_direction, monitor_enabled, rebuy_enabled,
                                rebuy_date, rebuy_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code.upper(), name, threshold_percent, target_price,
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
    return [dict(r) for r in rows]


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
