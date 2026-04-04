#!/usr/bin/env python3
"""
阶段买入 API 路由 (app/stage_buying/routes.py)
"""

import re
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

from .models import (
    get_all_stocks, get_stock_by_id, get_stock_by_code, add_stock,
    update_stock, delete_stock, is_code_exists,
    get_stage_details, get_stage_detail_by_id, update_stage_status,
    get_trigger_records, get_config, set_config,
)
from .service import (
    calculate_stages, create_stock_with_stages, update_stock_with_stages,
    get_stocks_with_current_info, refresh_stock_price, refresh_all_prices,
    toggle_stage_exec, check_and_trigger_stages, get_stock_summary,
)
from .utils import (
    send_stage_trigger_notification, send_test_notification,
    export_to_excel, import_from_excel,
)

stage_buying_bp = Blueprint('stage_buying', __name__, url_prefix='/api/stage-buying')


# ── 后台监控线程 ────────────────────────────────────────
_stage_monitor_running = False
_stage_monitor_thread = None


def _stage_monitor_loop():
    """阶段买入价格监控循环（每60秒检查一次）"""
    import time as _time
    while _stage_monitor_running:
        try:
            from .models import get_all_stocks, get_config
            from .service import check_and_trigger_stages
            from .utils import send_stage_trigger_notification

            stocks = get_all_stocks()
            for s in stocks:
                try:
                    triggered = check_and_trigger_stages(s['id'])
                    for t in triggered:
                        if get_config('feishu_enabled', 'true') == 'true':
                            st = t['stage']
                            stock = t['stock']
                            ok = send_stage_trigger_notification(
                                stock_name=stock['name'] or stock['code'],
                                stock_code=stock['code'],
                                current_price=t['current_price'],
                                stage_num=st['stage_number'],
                                buy_price=st['buy_price'],
                                shares=st['shares'],
                                trigger_time=t['trigger_time'],
                            )
                            if ok:
                                from .models import _get_db
                                conn = _get_db()
                                conn.cursor().execute(
                                    'UPDATE stage_trigger_records SET notified = 1 WHERE id = ?',
                                    (t['record_id'],)
                                )
                                conn.commit()
                                conn.close()
                except Exception:
                    pass
        except Exception:
            pass
        _time.sleep(60)


def _ensure_monitor_started():
    global _stage_monitor_running, _stage_monitor_thread
    if _stage_monitor_running:
        return
    _stage_monitor_running = True
    _stage_monitor_thread = threading.Thread(target=_stage_monitor_loop, daemon=True)
    _stage_monitor_thread.start()


def _ok(data=None, **extra):
    d = {'ok': True}
    if data is not None:
        d['data'] = data
    d.update(extra)
    return jsonify(d)


def _fail(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code


# ── 股票管理 ───────────────────────────────────────────

@stage_buying_bp.route('/stocks', methods=['GET'])
def api_list_stocks():
    _ensure_monitor_started()
    stocks = get_stocks_with_current_info()
    return _ok(stocks)


@stage_buying_bp.route('/stocks', methods=['POST'])
def api_add_stock():
    data = request.get_json()
    code_raw = (data.get('code') or '').strip()
    if not code_raw:
        return _fail('股票代码不能为空')

    # 代码格式校验（A股6位，美股字母）
    clean_raw = code_raw.upper()
    clean = re.sub(r'^(SH|SZ)', '', clean_raw)
    if not (re.match(r'^\d{6}$', clean) or re.match(r'^[A-Z]{2,5}$', clean)):
        return _fail('代码格式错误，A股为6位数字（如 601857），美股为2-5字母（如 AAPL）')

    if is_code_exists(clean):
        return _fail('该代码已存在')

    required = ['initial_price', 'initial_shares', 'per_stage_shares']
    for f in required:
        if f not in data or data[f] is None:
            return _fail(f'缺少必需字段: {f}')

    stock_id = create_stock_with_stages({**data, 'code': clean})
    return _ok({'id': stock_id})


@stage_buying_bp.route('/stocks/<int:stock_id>', methods=['PUT'])
def api_update_stock(stock_id: int):
    stock = get_stock_by_id(stock_id)
    if not stock:
        return _fail('股票不存在', 404)

    data = request.get_json()

    # 代码重复检查
    if 'code' in data:
        new_code = re.sub(r'^(SH|SZ)', '', data['code'].upper())
        if is_code_exists(new_code, exclude_id=stock_id):
            return _fail('新代码已存在')

    ok = update_stock_with_stages(stock_id, data)
    return _ok() if ok else _fail('更新失败')


@stage_buying_bp.route('/stocks/<int:stock_id>', methods=['DELETE'])
def api_delete_stock(stock_id: int):
    ok = delete_stock(stock_id)
    return _ok() if ok else _fail('删除失败')


@stage_buying_bp.route('/stocks/<int:stock_id>', methods=['GET'])
def api_get_stock(stock_id: int):
    stock = get_stock_by_id(stock_id)
    if not stock:
        return _fail('股票不存在', 404)
    stages = get_stage_details(stock_id)
    summary = get_stock_summary(stock_id)
    from services.stock_data import get_stock_price
    pd = get_stock_price(stock['code'])
    if pd:
        stock['current_price'] = pd.get('current_price')
        stock['change_percent'] = pd.get('change_percent')
        stock['price_name'] = pd.get('name', stock['name'])
    return _ok({**stock, 'stages': stages, 'summary': summary})


# ── 批量导入导出 ────────────────────────────────────────

@stage_buying_bp.route('/stocks/import', methods=['POST'])
def api_import_stocks():
    if 'file' not in request.files:
        return _fail('请上传 Excel 文件')
    f = request.files['file']
    if not f.filename.endswith(('.xlsx', '.xls')):
        return _fail('仅支持 .xlsx/.xls 文件')

    try:
        stocks = import_from_excel(f)
    except Exception as e:
        return _fail(f'导入失败: {e}')

    added = 0
    errors = []
    for s in stocks:
        if is_code_exists(s['code']):
            errors.append(f"{s['code']} 已存在，跳过")
            continue
        try:
            create_stock_with_stages(s)
            added += 1
        except Exception as e:
            errors.append(f"{s['code']} 导入失败: {e}")

    return _ok({'added': added, 'errors': errors})


@stage_buying_bp.route('/stocks/export', methods=['GET'])
def api_export_stocks():
    stocks = get_stocks_with_current_info()
    buf = export_to_excel(stocks)
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'stage_buying_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )


@stage_buying_bp.route('/stocks/refresh', methods=['POST'])
def api_refresh_prices():
    count = refresh_all_prices()
    return _ok({'refreshed': count})


# ── 阶段管理 ───────────────────────────────────────────

@stage_buying_bp.route('/stages/<int:stage_id>/exec', methods=['PUT'])
def api_toggle_exec(stage_id: int):
    ok, new_status = toggle_stage_exec(stage_id)
    if not ok:
        return _fail('状态切换失败，可能已是最终状态')
    return _ok({'status': new_status})


# ── 配置 ────────────────────────────────────────────────

@stage_buying_bp.route('/config', methods=['GET'])
def api_get_config():
    feishu_enabled = get_config('feishu_enabled', 'true')
    return _ok({
        'feishu_enabled': feishu_enabled == 'true',
    })


@stage_buying_bp.route('/config', methods=['PUT'])
def api_update_config():
    data = request.get_json()
    if 'feishu_enabled' in data:
        set_config('feishu_enabled', 'true' if data['feishu_enabled'] else 'false')
    return _ok()


@stage_buying_bp.route('/config/feishu/test', methods=['POST'])
def api_test_feishu():
    ok = send_test_notification()
    return _ok() if ok else _fail('发送失败')


# ── 触发记录 ─────────────────────────────────────────────

@stage_buying_bp.route('/trigger-records', methods=['GET'])
def api_get_records():
    stock_id = request.args.get('stock_id', type=int)
    code = request.args.get('code')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    # 如果按 code 过滤，先找 stock_id
    if code and not stock_id:
        s = get_stock_by_code(code)
        if s:
            stock_id = s['id']
    records = get_trigger_records(stock_id=stock_id, start_date=start_date, end_date=end_date)
    return _ok(records)
