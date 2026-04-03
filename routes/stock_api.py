#!/usr/bin/env python3
"""
股票管理 API 路由 (routes/stock_api.py)

【接口清单】

GET  /api/stocks
    获取所有正常股票（含实时价格）

POST /api/stocks
    添加股票
    Body: {code, name, threshold_percent, target_price}

GET  /api/stocks/deleted
    获取所有已删除股票（含实时价格）

PUT  /api/stocks/<code>
    更新股票信息，支持修改代码
    Body: {code?, name?, threshold_percent?, target_price?,
           monitor_enabled?, rebuy_enabled?, rebuy_date?, rebuy_time?}
    代码变更时通过「删除旧记录+插入新记录」实现

DELETE /api/stocks/<code>
    软删除股票（is_deleted=1）

POST /api/stocks/<code>/restore
    恢复已删除股票

DELETE /api/stocks/<code>/destroy
    彻底删除已删除股票

GET  /api/stocks/check-code?code=<code>&exclude=<exclude>
    检查股票代码格式及是否重复

GET  /api/interval
    获取监控间隔

PUT  /api/interval
    设置监控间隔
    Body: {interval_seconds}

GET  /api/price/<code>
    获取单只股票实时价格

GET  /api/stock-name/<code>
    根据代码获取股票名称

POST /api/test-notify
    发送飞书测试通知

【调用关系】
- 路由处理函数调用 models 层（get_all_stocks, add_stock, update_stock 等）
- 路由处理函数调用 services.stock_data（get_stock_price）
- 路由处理函数调用 services.feishu_notifier（send_test）
"""

from flask import Blueprint, request, jsonify

from models import (
    get_all_stocks, get_stock, add_stock, update_stock,
    delete_stock, get_interval, set_interval,
    restore_stock, permanent_delete_stock, is_code_exists,
    get_deleted_stocks,
)
from services.stock_data import get_stock_price
from services.feishu_notifier import send_test, clear_rebuy_notification
import sys
sys.path.insert(0, __file__.rsplit('/', 2)[0])
try:
    from logs.logger import log_api_error, log_api_info, log_stock_update, log_frontend_error
except ImportError:
    log_api_error = log_api_info = log_stock_update = log_frontend_error = lambda *a, **k: None

stock_bp = Blueprint('stock_api', __name__, url_prefix='/api')


def _enrich_stock(s: dict) -> dict:
    """为股票数据补充实时价格字段"""
    pd = get_stock_price(s['code'])
    if pd:
        s['current_price'] = pd['current_price']
        s['change_percent'] = pd['change_percent']
        s['update_time'] = pd['update_time']
        s['price_name'] = pd.get('name', s['name'])
    else:
        s['current_price'] = None
        s['change_percent'] = None
        s['update_time'] = None
        s['price_name'] = s['name']
    return s


@stock_bp.route('/stocks', methods=['GET'])
def api_list_stocks():
    from services.stock_data import batch_get_prices
    stocks = get_all_stocks()
    codes = [s['code'] for s in stocks]
    prices = batch_get_prices(codes)
    for s in stocks:
        pd = prices.get(s['code'])
        if pd:
            s['current_price'] = pd['current_price']
            s['change_percent'] = pd['change_percent']
            s['update_time'] = pd['update_time']
            s['price_name'] = pd.get('name', s['name'])
        else:
            s['current_price'] = None
            s['change_percent'] = None
            s['update_time'] = None
            s['price_name'] = s['name']
    return jsonify(stocks)


@stock_bp.route('/stocks', methods=['POST'])
def api_add_stock():
    data = request.get_json()
    code_raw = (data.get('code') or '').strip()
    if not code_raw:
        return jsonify({'ok': False, 'error': '股票代码不能为空'}), 400

    import re
    clean_raw = code_raw.strip().upper()
    clean = re.sub(r'^(SH|SZ)', '', clean_raw)
    # A股：6位数字；美股：2-5个大写字母
    if not (re.match(r'^\d{6}$', clean) or re.match(r'^[A-Z]{2,5}$', clean)):
        return jsonify({'ok': False, 'error': '代码格式错误，A股为6位数字（如 601857），美股为2-5字母（如 AAPL）'}), 400
    if is_code_exists(clean):
        return jsonify({'ok': False, 'error': '该代码已存在'}), 400

    pd = get_stock_price(clean)
    name = pd.get('name', '') if pd else data.get('name', '')
    current_price = pd.get('current_price') if pd else None

    target_price = float(data['target_price']) if data.get('target_price') else None
    
    # 自动判断目标价方向：
    # - 用户未显式指定 direction 时（字段不存在或为 None），根据 target_price 与当前价自动判断
    # - target_price >= 当前价 → 止盈监控(1)
    # - target_price < 当前价 → 买入监控(-1)
    explicit_direction = data.get('target_price_direction')
    if target_price is not None and explicit_direction is None:
        # 用户未显式指定方向，根据目标价与当前价自动判断
        if current_price is not None:
            target_price_direction = 1 if float(target_price) >= current_price else -1
        else:
            # 无法获取当前价，默认止盈
            target_price_direction = 1
    elif target_price is not None:
        # 用户显式指定方向，使用用户值
        target_price_direction = int(explicit_direction)
    else:
        target_price_direction = 1  # 无目标价时默认

    ok = add_stock(
        code=clean,
        name=name,
        threshold_percent=float(data.get('threshold_percent', 2.0)),
        target_price=target_price,
        target_price_direction=target_price_direction,
    )
    if not ok:
        return jsonify({'ok': False, 'error': '股票已存在或添加失败'}), 400
    return jsonify({'ok': True})


@stock_bp.route('/stocks/deleted', methods=['GET'])
def api_list_deleted_stocks():
    """获取所有已删除股票（供前端页面使用）"""
    from services.stock_data import batch_get_prices
    deleted_stocks = get_deleted_stocks()
    codes = [s['code'] for s in deleted_stocks]
    prices = batch_get_prices(codes)
    for s in deleted_stocks:
        pd = prices.get(s['code'])
        if pd:
            s['current_price'] = pd['current_price']
            s['change_percent'] = pd['change_percent']
            s['update_time'] = pd['update_time']
            s['price_name'] = pd.get('name', s['name'])
        else:
            s['current_price'] = None
            s['change_percent'] = None
            s['update_time'] = None
            s['price_name'] = s['name']
    return jsonify(deleted_stocks)


@stock_bp.route('/stocks/<code>', methods=['PUT'])
def api_update_stock(code: str):
    """
    更新股票信息，支持修改代码。
    若 payload.code 与 URL code 不同，走代码变更流程
    （删除旧记录 + 插入新记录）。
    """
    data = request.get_json()
    old_code = code.upper()
    log_api_info(f"UPDATE request", {"old_code": old_code, "data": data})

    new_code = (data.get('code') or '').strip().upper()
    # 判断是否真的需要变更代码：new_code 存在且与 old_code 不同
    code_changed = bool(new_code) and new_code != old_code

    if code_changed:
        import re
        clean = re.sub(r'^(SH|SZ)', '', new_code)
        if not (re.match(r'^\d{6}$', clean) or re.match(r'^[A-Z]{2,5}$', clean)):
            log_api_error("UPDATE stock", f"Code format invalid: {new_code}")
            return jsonify({'ok': False, 'error': '代码格式错误，A股为6位数字（如 601857），美股为2-5字母（如 AAPL）'}), 400
        if is_code_exists(clean, exclude_code=old_code):
            log_api_error("UPDATE stock", f"New code already exists: {clean}")
            return jsonify({'ok': False, 'error': '新代码已存在'}), 400
        old = get_stock(old_code)
        if not old:
            log_api_error("UPDATE stock", f"Old stock not found: {old_code}")
            return jsonify({'ok': False, 'error': '原股票不存在'}), 404

        # 代码变更流程：删除旧记录 + 插入新记录
        del_ok = delete_stock(old_code)
        if not del_ok:
            log_api_error("UPDATE stock", f"Failed to delete old stock: {old_code}")
            # 软删除失败（可能已被删除），尝试直接新增
        log_stock_update("CODE_CHANGE", old_code, old, {"code": clean, **data})

        # 自动判断目标价方向
        new_target_price = float(data['target_price']) if data.get('target_price') is not None else old.get('target_price')
        explicit_dir = data.get('target_price_direction')
        if data.get('target_price') is not None and explicit_dir is None:
            # 目标价变更且用户未指定方向，根据当前价自动判断
            pd_new = get_stock_price(clean)
            cur_price = pd_new.get('current_price') if pd_new else None
            if cur_price is not None:
                new_direction = 1 if new_target_price >= cur_price else -1
            else:
                new_direction = 1
        else:
            new_direction = int(explicit_dir) if explicit_dir is not None else int(old.get('target_price_direction', 1))

        add_stock(
            code=clean,
            name=data.get('name', old.get('name', '')),
            threshold_percent=float(data.get('threshold_percent', old.get('threshold_percent', 2.0))),
            target_price=new_target_price,
            target_price_direction=new_direction,
            monitor_enabled=int(data.get('monitor_enabled', old.get('monitor_enabled', 1))),
            rebuy_enabled=int(data.get('rebuy_enabled', old.get('rebuy_enabled', 0))),
            rebuy_date=data.get('rebuy_date', old.get('rebuy_date')),
            rebuy_time=data.get('rebuy_time', old.get('rebuy_time', '09:00:00')),
        )
        log_api_info(f"UPDATE stock", f"Code changed: {old_code} -> {clean}")
        return jsonify({'ok': True})

    if not data:
        log_api_error("UPDATE stock", "No data provided")
        return jsonify({'ok': False, 'error': '无更新字段'}), 400

    # 无代码变更：直接更新其他字段
    # 若 rebuy 相关字段变更，清除旧的触发状态（避免用旧日期key拦截新时间）
    rebuy_fields = {'rebuy_date', 'rebuy_time', 'rebuy_enabled'}
    if rebuy_fields & set(data.keys()):
        old = get_stock(old_code)
        if old and old.get('rebuy_date'):
            clear_rebuy_notification(old_code, old['rebuy_date'])

    # 若 target_price 变更且用户未指定方向，自动判断
    if 'target_price' in data and data.get('target_price') is not None and 'target_price_direction' not in data:
        old = get_stock(old_code)
        pd_new = get_stock_price(old_code)
        cur_price = pd_new.get('current_price') if pd_new else None
        if cur_price is not None:
            new_dir = 1 if float(data['target_price']) >= cur_price else -1
        else:
            new_dir = 1
        data = {**data, 'target_price_direction': new_dir}

    ok = update_stock(old_code, **data)
    if ok:
        log_api_info(f"UPDATE stock", f"Updated fields for {old_code}")
    else:
        log_api_error("UPDATE stock", f"Update returned False for {old_code}", data)
    return jsonify({'ok': ok})


@stock_bp.route('/stocks/<code>', methods=['DELETE'])
def api_delete_stock(code: str):
    """软删除：标记 is_deleted=1"""
    ok = delete_stock(code.upper())
    return jsonify({'ok': ok})


@stock_bp.route('/stocks/<code>/restore', methods=['POST'])
def api_restore_stock(code: str):
    """恢复已删除股票为正常状态"""
    ok = restore_stock(code.upper())
    if not ok:
        return jsonify({'ok': False, 'error': '恢复失败，股票不存在'}), 404
    return jsonify({'ok': True})


@stock_bp.route('/stocks/<code>/destroy', methods=['DELETE'])
def api_destroy_stock(code: str):
    """彻底删除：仅限 is_deleted=1 的记录，永久移除"""
    ok = permanent_delete_stock(code.upper())
    if not ok:
        return jsonify({'ok': False, 'error': '彻底删除失败，股票不存在'}), 404
    return jsonify({'ok': True})


@stock_bp.route('/stocks/check-code', methods=['GET'])
def api_check_code():
    """检查股票代码格式是否合法 + 是否已存在"""
    code = (request.args.get('code') or '').strip().lower()
    exclude = (request.args.get('exclude') or '').strip().lower()
    if not code:
        return jsonify({'ok': False, 'error': '代码不能为空'}), 400

    import re
    clean = re.sub(r'^(sh|sz)', '', code.upper())
    if not (re.match(r'^\d{6}$', clean) or re.match(r'^[A-Z]{2,5}$', clean)):
        return jsonify({'ok': False, 'error': '代码格式错误，A股为6位数字（如 601857），美股为2-5字母（如 AAPL）'}), 400

    if is_code_exists(clean, exclude):
        return jsonify({'ok': False, 'error': '该代码已存在'}), 400

    return jsonify({'ok': True})


@stock_bp.route('/interval', methods=['GET'])
def api_get_interval():
    return jsonify({'interval_seconds': get_interval()})


@stock_bp.route('/interval', methods=['PUT'])
def api_set_interval():
    data = request.get_json()
    seconds = int(data.get('interval_seconds', 60))
    if seconds < 10:
        return jsonify({'ok': False, 'error': '间隔不能小于10秒'}), 400
    set_interval(seconds)
    return jsonify({'ok': True})


@stock_bp.route('/price/<code>')
def api_price(code: str):
    pd = get_stock_price(code)
    if pd:
        return jsonify(pd)
    return jsonify({'error': '获取股价失败'}), 400


@stock_bp.route('/stock-name/<code>')
def api_stock_name(code: str):
    """根据代码获取股票名称"""
    pd = get_stock_price(code)
    if pd:
        return jsonify({'name': pd.get('name', ''), 'ok': True})
    return jsonify({'name': '', 'ok': False})


@stock_bp.route('/test-notify', methods=['POST'])
def api_test_notify():
    ok = send_test()
    return jsonify({'ok': ok})


@stock_bp.route('/frontend-error', methods=['POST'])
def api_frontend_error():
    """接收前端JS错误并记录到日志"""
    data = request.get_json() or {}
    operation = data.get('operation', 'unknown')
    error = data.get('error', '')
    context = data.get('context', {})
    log_frontend_error(operation, error, context)
    return jsonify({'ok': True})
