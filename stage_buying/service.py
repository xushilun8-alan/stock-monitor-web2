#!/usr/bin/env python3
"""
阶段买入业务逻辑 (app/stage_buying/service.py)
"""

import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from . import models
from services.stock_data import get_stock_price


# ── 核心算法 ──────────────────────────────────────────────

def _round8(x: float) -> float:
    """保留8位小数"""
    return math.floor(x * 1e8 + 0.5) / 1e8


def calculate_stages(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    按公式计算所有阶段详情

    参数:
        initial_price: 初始单价
        initial_shares: 初始股数（阶段1股数）
        per_stage_shares: 每阶股数
        stage_count: 总阶段数
        serial_coefficient: 序号系数
        amplitude_coefficient: 幅度系数
        decline_coefficient: 跌幅系数
        target_price: 目标价基准（可None）
        min_amplitude: 最小幅度（保留字段）
        amplitude_multiplier: 幅度乘数
        floor_price: 底价（可None）
    """
    initial_price = float(params['initial_price'])
    initial_shares = int(params['initial_shares'])
    per_stage_shares = int(params['per_stage_shares'])
    stage_count = int(params.get('stage_count', 9))
    serial_coefficient = float(params.get('serial_coefficient', 1.0))
    amplitude_coefficient = float(params.get('amplitude_coefficient', 0.08))
    decline_coefficient = float(params.get('decline_coefficient', 0.975))
    target_price = float(params['target_price']) if params.get('target_price') is not None else None
    min_amplitude = float(params.get('min_amplitude', 0.98))
    amplitude_multiplier = float(params.get('amplitude_multiplier', 1.001))
    floor_price = float(params['floor_price']) if params.get('floor_price') is not None else None

    stages = []
    prev_buy_price = initial_price
    prev_amplitude = None

    for n in range(1, stage_count + 1):
        # 1. 计算幅度
        if n == 1:
            amplitude = 1.0
        elif n == 2:
            amplitude = decline_coefficient * (serial_coefficient - 0.1 + amplitude_coefficient)
        elif n == 3:
            amplitude = prev_amplitude * 1.01
        else:
            amplitude = prev_amplitude * (amplitude_multiplier ** (n - 2))

        amplitude = _round8(amplitude)

        # 幅度上限：若计算值大于最小幅度设定值，强制取最小幅度
        if n > 1 and amplitude > min_amplitude:
            amplitude = _round8(min_amplitude)

        # 2. 计算买入单价
        if n == 1:
            buy_price = initial_price
        else:
            buy_price = prev_buy_price * amplitude

        buy_price = _round8(buy_price)

        # 3. 股数与金额
        if n == 1:
            shares = initial_shares
        else:
            shares = per_stage_shares
        buy_amount = _round8(buy_price * shares)

        # 4. 底价亏损
        # 公式：阶段1 = 底价*初始股数-当阶金额；非阶段1 = 底价*每阶股数-当阶金额
        # 结果<0表示亏损（底价比当前买入价高），>0表示盈利
        floor_loss = None
        loss_rate = None
        if floor_price is not None:
            if n == 1:
                floor_loss = floor_price * initial_shares - buy_amount
            else:
                floor_loss = floor_price * per_stage_shares - buy_amount
            floor_loss = _round8(floor_loss)
            if buy_amount != 0:
                loss_rate = _round8(floor_loss / buy_amount * 100)

        # 5. 目标收益
        target_income = None
        expected_return = None
        return_rate = None
        if target_price is not None:
            if n == 1:
                target_income = target_price * initial_shares
            else:
                target_income = target_price * per_stage_shares
            target_income = _round8(target_income)
            expected_return = _round8(target_income - buy_amount)
            if buy_amount != 0:
                return_rate = _round8(expected_return / buy_amount * 100)

        stages.append({
            'stage_number': n,
            'amplitude': amplitude,
            'buy_price': buy_price,
            'shares': shares,
            'buy_amount': buy_amount,
            'floor_loss': floor_loss,
            'loss_rate': loss_rate,
            'target_income': target_income,
            'expected_return': expected_return,
            'return_rate': return_rate,
            'status': 'untriggered',
        })

        prev_buy_price = buy_price
        prev_amplitude = amplitude

    return stages


# ── 业务操作 ──────────────────────────────────────────────

def create_stock_with_stages(data: Dict[str, Any]) -> int:
    """
    添加股票并计算所有阶段详情
    返回 stock_id
    """
    # 获取股票名称（如果未提供）
    name = data.get('name', '')
    if not name:
        pd = get_stock_price(data['code'])
        if pd:
            name = pd.get('name', '')

    stock_data = {**data, 'name': name}
    stock_id = models.add_stock(stock_data)
    stages = calculate_stages(data)
    models.save_stage_details(stock_id, stages)
    return stock_id


def update_stock_with_stages(stock_id: int, data: Dict[str, Any]) -> bool:
    """
    更新股票参数并重新计算所有阶段详情
    """
    # 获取名称（如果未提供且代码变更）
    if 'code' in data and 'name' not in data:
        pd = get_stock_price(data['code'])
        if pd:
            data = {**data, 'name': pd.get('name', '')}

    ok = models.update_stock(stock_id, data)
    if not ok:
        return False

    # 重新计算阶段（保留已执行状态）
    old_stages = {s['stage_number']: s for s in models.get_stage_details(stock_id)}
    new_stages = calculate_stages(data)

    # 保留已执行状态
    for ns in new_stages:
        old = old_stages.get(ns['stage_number'], {})
        if old.get('status') == 'executed':
            ns['status'] = 'executed'

    models.save_stage_details(stock_id, new_stages)
    return True


def get_stocks_with_current_info() -> List[Dict[str, Any]]:
    """
    获取所有股票，并补充实时价格、当前阶段、下阶段买入价等信息
    """
    stocks = models.get_all_stocks()
    for s in stocks:
        # 实时价格
        pd = get_stock_price(s['code'])
        if pd:
            s['current_price'] = pd.get('current_price')
            s['change_percent'] = pd.get('change_percent')
            s['update_time'] = pd.get('update_time')
            s['price_name'] = pd.get('name', s['name'])
        else:
            s['current_price'] = None
            s['change_percent'] = None
            s['update_time'] = None
            s['price_name'] = s['name']

        # 阶段详情
        stages = models.get_stage_details(s['id'])
        s['stages'] = stages

        # 当前阶段（最新未触发或已触发状态的序号）
        current_stage_num = 1
        executed_count = 0
        for st in stages:
            if st['status'] == 'executed':
                executed_count += 1
            if st['status'] in ('untriggered', 'triggered'):
                current_stage_num = st['stage_number']

        s['current_stage'] = current_stage_num
        s['executed_count'] = executed_count
        s['total_stages'] = len(stages)

        # 下一阶段买入价
        next_stage = next((st for st in stages if st['status'] == 'untriggered'), None)
        s['next_buy_price'] = next_stage['buy_price'] if next_stage else None

        # 距离下一阶段跌幅
        if s['current_price'] is not None and next_stage:
            cp = s['current_price']
            nbp = next_stage['buy_price']
            if nbp > 0:
                s['drop_to_next_pct'] = _round8((cp - nbp) / cp * 100)
            else:
                s['drop_to_next_pct'] = None
        else:
            s['drop_to_next_pct'] = None

        # 汇总
        total_amount = sum(st['buy_amount'] for st in stages)
        executed_amount = sum(st['buy_amount'] for st in stages if st['status'] == 'executed')
        s['total_investment'] = _round8(total_amount)
        s['executed_investment'] = _round8(executed_amount)

        # ── 新增两项汇总统计（全部阶段，非仅已执行）────────────────────
        total_expected = sum((st['expected_return'] or 0) for st in stages)
        total_floor_loss = sum((st['floor_loss'] or 0) for st in stages)

        # 盈利亏损比 = -全部阶段汇总期望收益 / 全部阶段汇总底价亏损
        if total_floor_loss != 0:
            s['profit_loss_ratio'] = _round8(-total_expected / total_floor_loss)
        else:
            s['profit_loss_ratio'] = None

        # 收益成本比 = (全部阶段汇总期望收益 / 全部阶段汇总金额) × 100%
        if total_amount != 0:
            s['return_cost_ratio'] = _round8(total_expected / total_amount * 100)
        else:
            s['return_cost_ratio'] = None

    return stocks


def refresh_stock_price(stock_id: int) -> Optional[float]:
    """刷新单只股票价格，返回当前价格"""
    s = models.get_stock_by_id(stock_id)
    if not s:
        return None
    pd = get_stock_price(s['code'])
    return pd.get('current_price') if pd else None


def refresh_all_prices() -> int:
    """刷新所有股票价格，返回成功数量"""
    stocks = models.get_all_stocks()
    count = 0
    for s in stocks:
        pd = get_stock_price(s['code'])
        if pd and pd.get('current_price'):
            count += 1
    return count


def toggle_stage_exec(stage_id: int) -> Tuple[bool, str]:
    """
    切换阶段执行状态
    triggered -> executed
    executed -> triggered
    untriggered -> 无操作
    返回 (成功, 新状态)
    """
    stage = models.get_stage_detail_by_id(stage_id)
    if not stage:
        return False, ''

    if stage['status'] == 'triggered':
        ok = models.update_stage_status(stage_id, 'executed')
        return ok, 'executed'
    elif stage['status'] == 'executed':
        ok = models.update_stage_status(stage_id, 'triggered')
        return ok, 'triggered'
    else:
        return False, stage['status']


def recalculate_single_stage(stage_id: int, new_shares: int) -> Optional[Dict[str, Any]]:
    """
    仅更新单阶段股数并重算关联指标
    buy_price/amplitude/target_price/floor_price 等基础参数不变
    返回更新后的 stage dict
    """
    stage = models.get_stage_detail_by_id(stage_id)
    if not stage:
        return None

    stock = models.get_stock_by_id(stage['stock_id'])
    if not stock:
        return None

    # buy_price 不随 shares 变化（由 amplitude 计算决定）
    buy_price = stage['buy_price']
    buy_amount = _round8(buy_price * new_shares)

    floor_price = stock['floor_price']
    target_price = stock['target_price']

    # 底价亏损 = 底价 * 当阶股数 - 当阶金额（亏损为负）
    # 公式：阶段1 = 底价*初始股数-当阶金额；非阶段1 = 底价*每阶股数-当阶金额
    floor_loss = None
    loss_rate = None
    if floor_price is not None:
        floor_loss = floor_price * new_shares - buy_amount
        floor_loss = _round8(floor_loss)
        if buy_amount != 0:
            loss_rate = _round8(floor_loss / buy_amount * 100)

    # 目标收益 / 期望收益 / 收益率（统一用当阶实际股数 new_shares）
    target_income = None
    expected_return = None
    return_rate = None
    if target_price is not None:
        target_income = _round8(target_price * new_shares)
        expected_return = _round8(target_income - buy_amount)
        if buy_amount != 0:
            return_rate = _round8(expected_return / buy_amount * 100)

    # 写入数据库
    models.update_stage_shares(stage_id, new_shares)
    conn = models._get_db()
    c = conn.cursor()
    c.execute('''
        UPDATE stage_details SET
            buy_amount = ?, floor_loss = ?, loss_rate = ?,
            target_income = ?, expected_return = ?, return_rate = ?
        WHERE id = ?
    ''', (buy_amount, floor_loss, loss_rate, target_income, expected_return, return_rate, stage_id))
    conn.commit()
    conn.close()

    return models.get_stage_detail_by_id(stage_id)


def check_and_trigger_stages(stock_id: int) -> List[Dict[str, Any]]:
    """
    检查股票当前价格是否触发未触发阶段
    触发条件：current_price <= buy_price 且 status == 'untriggered'
    返回触发的阶段列表
    """
    s = models.get_stock_by_id(stock_id)
    if not s:
        return []

    pd = get_stock_price(s['code'])
    if not pd or pd.get('current_price') is None:
        return []

    current_price = pd['current_price']
    stages = models.get_stage_details(stock_id)
    triggered = []

    for st in stages:
        if st['status'] != 'untriggered':
            continue
        if current_price <= st['buy_price']:
            # 触发
            models.update_stage_status(st['id'], 'triggered')
            now = datetime.now().isoformat()
            rec_id = models.add_trigger_record(
                stock_id, st['id'], now, current_price, notified=0
            )
            triggered.append({
                'record_id': rec_id,
                'stage': {**st, 'status': 'triggered'},
                'current_price': current_price,
                'trigger_time': now,
                'stock': s,
            })

    return triggered


def get_stock_summary(stock_id: int) -> Dict[str, Any]:
    """获取股票汇总统计"""
    s = models.get_stock_by_id(stock_id)
    if not s:
        return {}
    stages = models.get_stage_details(stock_id)

    total_amount = sum(st['buy_amount'] for st in stages)
    executed_amount = sum(st['buy_amount'] for st in stages if st['status'] == 'executed')
    total_expected = sum((st['expected_return'] or 0) for st in stages if st['status'] == 'executed')
    total_floor_loss = sum((st['floor_loss'] or 0) for st in stages if st['status'] == 'executed')

    # 全部阶段汇总（用于盈利亏损比 & 收益成本比）
    all_expected = sum((st['expected_return'] or 0) for st in stages)
    all_floor_loss = sum((st['floor_loss'] or 0) for st in stages)

    if all_floor_loss != 0:
        profit_loss_ratio = _round8(-all_expected / all_floor_loss)
    else:
        profit_loss_ratio = None
    if total_amount != 0:
        return_cost_ratio = _round8(all_expected / total_amount * 100)
    else:
        return_cost_ratio = None

    return {
        'total_stages': len(stages),
        'executed_stages': sum(1 for st in stages if st['status'] == 'executed'),
        'triggered_stages': sum(1 for st in stages if st['status'] == 'triggered'),
        'total_investment': _round8(total_amount),
        'executed_investment': _round8(executed_amount),
        'total_expected_return': _round8(total_expected),
        'total_floor_loss': _round8(total_floor_loss),
        'profit_loss_ratio': profit_loss_ratio,
        'return_cost_ratio': return_cost_ratio,
    }
