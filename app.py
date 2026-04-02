#!/usr/bin/env python3
"""
股票监控系统 Web 主应用 (app.py)

【启动方式】
    python run.py
    或
    python app.py

【架构说明】
- app.py: Flask 应用工厂 + 页面渲染路由（/ 和 /deleted）
- routes/stock_api.py: 所有 /api/* 接口（注册为 Blueprint）
- models/: 数据库模型层
- services/stock_data.py: 股价数据获取服务
- services/feishu_notifier.py: 飞书通知服务
- services/monitor.py: 后台监控调度服务

【页面路由】
- GET /: 股票监控主页
- GET /deleted: 已删除股票管理页

【API 路由】(由 routes.stock_api.stock_bp 提供)
- GET/POST      /api/stocks
- GET           /api/stocks/deleted
- PUT           /api/stocks/<code>
- DELETE        /api/stocks/<code>
- POST          /api/stocks/<code>/restore
- DELETE        /api/stocks/<code>/destroy
- GET           /api/stocks/check-code
- GET/PUT       /api/interval
- GET           /api/price/<code>
- GET           /api/stock-name/<code>
- POST          /api/test-notify

【监控】
启动时自动调用 start_monitor() 启动后台监控线程
"""

import os
import sys

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, jsonify, request, send_from_directory
from services.stock_data import get_stock_price
from services.monitor import start_monitor

# 注册 API Blueprint（晚于 models 初始化）
from routes.stock_api import stock_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'stock-monitor-secret-2026')

    # 注册 API 路由
    app.register_blueprint(stock_bp)

    # 启动后台监控
    start_monitor()

    # ── 页面渲染路由 ──────────────────────────────────────────

    # ── SPA 静态文件路由（生产模式：非 debug 时生效）────────────
    vue_dist = os.path.join(os.path.dirname(__file__), 'vue-project', 'dist')

    @app.route('/')
    def index():
        if not app.debug and os.path.isdir(vue_dist):
            return send_from_directory(vue_dist, 'index.html')
        from models import get_all_stocks, get_deleted_stocks, get_interval
        stocks = get_all_stocks()
        interval = get_interval()
        deleted_stocks = get_deleted_stocks()
        return render_template('index.html', stocks=stocks, interval=interval,
                               deleted_count=len(deleted_stocks))

    @app.route('/deleted')
    def deleted_page():
        if not app.debug and os.path.isdir(vue_dist):
            return send_from_directory(vue_dist, 'index.html')
        from models import get_deleted_stocks, get_interval
        deleted_stocks = get_deleted_stocks()
        interval = get_interval()
        return render_template('index.html', stocks=[], interval=interval,
                               deleted_stocks=deleted_stocks, deleted_count=len(deleted_stocks),
                               page='deleted')

    # ── 静态资源（生产模式）───────────────────────────────────
    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        if not app.debug and os.path.isdir(vue_dist):
            return send_from_directory(os.path.join(vue_dist, 'assets'), filename)
        return '', 404

    return app


# 兼容直接运行
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5188, debug=True)
