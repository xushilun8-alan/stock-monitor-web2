#!/usr/bin/env python3
"""
阶段买入数据库模型 (app/stage_buying/models.py)
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stage_buying.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stage_stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT,
            initial_price REAL NOT NULL,
            initial_shares INTEGER NOT NULL,
            per_stage_shares INTEGER NOT NULL,
            stage_count INTEGER NOT NULL DEFAULT 9,
            serial_coefficient REAL NOT NULL DEFAULT 1.0,
            amplitude_coefficient REAL NOT NULL DEFAULT 0.08,
            decline_coefficient REAL NOT NULL DEFAULT 0.975,
            target_price REAL,
            min_amplitude REAL NOT NULL DEFAULT 0.98,
            amplitude_multiplier REAL NOT NULL DEFAULT 1.001,
            floor_price REAL,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS stage_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            stage_number INTEGER NOT NULL,
            amplitude REAL NOT NULL,
            buy_price REAL NOT NULL,
            shares INTEGER NOT NULL,
            buy_amount REAL NOT NULL,
            floor_loss REAL,
            loss_rate REAL,
            target_income REAL,
            expected_return REAL,
            return_rate REAL,
            status TEXT DEFAULT 'untriggered',
            FOREIGN KEY (stock_id) REFERENCES stage_stocks(id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS stage_trigger_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            stage_id INTEGER NOT NULL,
            trigger_time TEXT NOT NULL,
            current_price REAL NOT NULL,
            notified INTEGER DEFAULT 0,
            FOREIGN KEY (stock_id) REFERENCES stage_stocks(id) ON DELETE CASCADE,
            FOREIGN KEY (stage_id) REFERENCES stage_details(id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS stage_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # 外键支持
    try:
        c.execute('PRAGMA foreign_keys = ON')
    except Exception:
        pass
    conn.commit()
    conn.close()


# ── 股票 CRUD ──────────────────────────────────────────────

def get_all_stocks() -> List[Dict[str, Any]]:
    conn = _get_db()
    c = conn.cursor()
    rows = c.execute('SELECT * FROM stage_stocks ORDER BY code').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stock_by_id(stock_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM stage_stocks WHERE id = ?', (stock_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_stock_by_code(code: str) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM stage_stocks WHERE code = ?', (code.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_stock(data: Dict[str, Any]) -> int:
    """返回新记录ID"""
    conn = _get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''
        INSERT INTO stage_stocks (
            code, name, initial_price, initial_shares, per_stage_shares,
            stage_count, serial_coefficient, amplitude_coefficient,
            decline_coefficient, target_price, min_amplitude,
            amplitude_multiplier, floor_price, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['code'].upper(),
        data.get('name', ''),
        data['initial_price'],
        data['initial_shares'],
        data['per_stage_shares'],
        data.get('stage_count', 9),
        data.get('serial_coefficient', 1.0),
        data.get('amplitude_coefficient', 0.08),
        data.get('decline_coefficient', 0.975),
        data.get('target_price'),
        data.get('min_amplitude', 0.98),
        data.get('amplitude_multiplier', 1.001),
        data.get('floor_price'),
        now, now
    ))
    conn.commit()
    stock_id = c.lastrowid
    conn.close()
    return stock_id


def update_stock(stock_id: int, data: Dict[str, Any]) -> bool:
    allowed = ['name', 'initial_price', 'initial_shares', 'per_stage_shares',
               'stage_count', 'serial_coefficient', 'amplitude_coefficient',
               'decline_coefficient', 'target_price', 'min_amplitude',
               'amplitude_multiplier', 'floor_price']
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return False
    updates['updated_at'] = datetime.now().isoformat()
    conn = _get_db()
    c = conn.cursor()
    set_clause = ', '.join([f"{k} = ?" for k in updates])
    values = list(updates.values()) + [stock_id]
    c.execute(f'UPDATE stage_stocks SET {set_clause} WHERE id = ?', values)
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def delete_stock(stock_id: int) -> bool:
    conn = _get_db()
    c = conn.cursor()
    c.execute('DELETE FROM stage_stocks WHERE id = ?', (stock_id,))
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def is_code_exists(code: str, exclude_id: int = None) -> bool:
    conn = _get_db()
    c = conn.cursor()
    if exclude_id:
        row = c.execute(
            'SELECT id FROM stage_stocks WHERE code = ? AND id != ?',
            (code.upper(), exclude_id)
        ).fetchone()
    else:
        row = c.execute(
            'SELECT id FROM stage_stocks WHERE code = ?',
            (code.upper(),)
        ).fetchone()
    conn.close()
    return row is not None


# ── 阶段详情 CRUD ─────────────────────────────────────────

def get_stage_details(stock_id: int) -> List[Dict[str, Any]]:
    conn = _get_db()
    c = conn.cursor()
    rows = c.execute(
        'SELECT * FROM stage_details WHERE stock_id = ? ORDER BY stage_number',
        (stock_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stage_detail_by_id(stage_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    c = conn.cursor()
    row = c.execute('SELECT * FROM stage_details WHERE id = ?', (stage_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_stage_details(stock_id: int, stages: List[Dict[str, Any]]) -> None:
    """批量插入阶段详情（先删后插）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute('DELETE FROM stage_details WHERE stock_id = ?', (stock_id,))
    for s in stages:
        c.execute('''
            INSERT INTO stage_details (
                stock_id, stage_number, amplitude, buy_price, shares,
                buy_amount, floor_loss, loss_rate, target_income,
                expected_return, return_rate, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stock_id, s['stage_number'], s['amplitude'], s['buy_price'],
            s['shares'], s['buy_amount'], s.get('floor_loss'),
            s.get('loss_rate'), s.get('target_income'),
            s.get('expected_return'), s.get('return_rate'),
            s.get('status', 'untriggered')
        ))
    conn.commit()
    conn.close()


def update_stage_status(stage_id: int, status: str) -> bool:
    conn = _get_db()
    c = conn.cursor()
    c.execute('UPDATE stage_details SET status = ? WHERE id = ?', (status, stage_id))
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


def update_stage_shares(stage_id: int, shares: int) -> bool:
    conn = _get_db()
    c = conn.cursor()
    c.execute('UPDATE stage_details SET shares = ? WHERE id = ?', (shares, stage_id))
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return ok


# ── 触发记录 CRUD ─────────────────────────────────────────

def get_trigger_records(stock_id: int = None,
                         start_date: str = None,
                         end_date: str = None) -> List[Dict[str, Any]]:
    conn = _get_db()
    c = conn.cursor()
    sql = '''SELECT r.*, s.code, s.name, d.stage_number
             FROM stage_trigger_records r
             JOIN stage_stocks s ON r.stock_id = s.id
             LEFT JOIN stage_details d ON r.stage_id = d.id
             WHERE 1=1'''
    params = []
    if stock_id:
        sql += ' AND r.stock_id = ?'
        params.append(stock_id)
    if start_date:
        sql += ' AND r.trigger_time >= ?'
        params.append(start_date)
    if end_date:
        sql += ' AND r.trigger_time <= ?'
        params.append(end_date)
    sql += ' ORDER BY r.trigger_time DESC'
    rows = c.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_trigger_record(stock_id: int, stage_id: int,
                        trigger_time: str, current_price: float,
                        notified: int = 0) -> int:
    conn = _get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO stage_trigger_records
        (stock_id, stage_id, trigger_time, current_price, notified)
        VALUES (?, ?, ?, ?, ?)
    ''', (stock_id, stage_id, trigger_time, current_price, notified))
    conn.commit()
    rec_id = c.lastrowid
    conn.close()
    return rec_id


def mark_record_notified(record_id: int) -> None:
    conn = _get_db()
    c = conn.cursor()
    c.execute('UPDATE stage_trigger_records SET notified = 1 WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()


def is_stage_triggered(stock_id: int, stage_id: int) -> bool:
    """检查某阶段是否已有触发记录"""
    conn = _get_db()
    c = conn.cursor()
    row = c.execute(
        'SELECT id FROM stage_trigger_records WHERE stock_id = ? AND stage_id = ?',
        (stock_id, stage_id)
    ).fetchone()
    conn.close()
    return row is not None


# ── 配置 ──────────────────────────────────────────────────

def get_config(key: str, default: str = None) -> Optional[str]:
    conn = _get_db()
    c = conn.cursor()
    row = c.execute('SELECT value FROM stage_config WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_config(key: str, value: str) -> None:
    conn = _get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO stage_config VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()


# ── 初始化 ────────────────────────────────────────────────
init_db()
