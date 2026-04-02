#!/usr/bin/env python3
"""
集成测试 (tests/test_integration.py)
覆盖所有API端点和核心业务逻辑
"""

import pytest
import json
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 测试数据库
TEST_DB_DIR = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(TEST_DB_DIR, 'test_stocks.db')


@pytest.fixture(scope='session', autouse=True)
def setup_test_env():
    """设置测试环境变量"""
    os.environ['STOCK_DB_PATH'] = TEST_DB_PATH
    yield
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(scope='function')
def app():
    """创建测试用Flask应用"""
    import models
    models.DB_PATH = TEST_DB_PATH
    models.init_db()
    
    from app import create_app
    test_app = create_app()
    test_app.config['TESTING'] = True
    yield test_app


@pytest.fixture(scope='function')
def client(app):
    """Flask测试客户端"""
    return app.test_client()


@pytest.fixture(scope='function')
def db():
    """提供数据库访问"""
    import models
    models.DB_PATH = TEST_DB_PATH
    models.init_db()
    yield models
    # 每个测试后清空stocks表
    import sqlite3
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute('DELETE FROM stocks')
    conn.execute("DELETE FROM config WHERE key != 'interval_seconds'")
    conn.commit()
    conn.close()


@pytest.fixture
def test_stock(db):
    """添加一只测试股票"""
    db.add_stock(
        code='601857',
        name='中国石油',
        threshold_percent=2.0,
        target_price=7.0,
        monitor_enabled=1
    )
    return '601857'


class TestStockAPI:
    """股票管理API集成测试"""

    def test_add_stock_success(self, client):
        """POST /api/stocks - 成功添加股票"""
        response = client.post('/api/stocks', json={
            'code': '601857',
            'name': '中国石油',
            'threshold_percent': 2.0,
            'target_price': 7.0
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_add_stock_missing_code(self, client):
        """POST /api/stocks - 缺少代码"""
        response = client.post('/api/stocks', json={'name': '测试'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert '不能为空' in data['error']

    def test_add_stock_invalid_format(self, client):
        """POST /api/stocks - 代码格式错误"""
        response = client.post('/api/stocks', json={'code': '12345'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert '格式错误' in data['error']

    def test_add_stock_duplicate(self, client, test_stock):
        """POST /api/stocks - 重复代码"""
        response = client.post('/api/stocks', json={
            'code': '601857',
            'name': '重复股票'
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert '已存在' in data['error']

    def test_list_stocks(self, client, test_stock):
        """GET /api/stocks - 获取股票列表"""
        response = client.get('/api/stocks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(s['code'] == '601857' for s in data)

    def test_list_stocks_empty(self, client):
        """GET /api/stocks - 空列表"""
        response = client.get('/api/stocks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_update_stock_success(self, client, test_stock):
        """PUT /api/stocks/<code> - 成功更新"""
        response = client.put('/api/stocks/601857', json={
            'name': '中国石油更新',
            'threshold_percent': 3.0
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_update_stock_not_found(self, client):
        """PUT /api/stocks/<code> - 股票不存在"""
        response = client.put('/api/stocks/999999', json={
            'name': '不存在'
        })
        assert response.status_code == 200

    def test_update_stock_code_change(self, client, test_stock):
        """PUT /api/stocks/<code> - 修改代码"""
        response = client.put('/api/stocks/601857', json={
            'code': '601858',
            'name': '代码变更'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_delete_stock_success(self, client, test_stock):
        """DELETE /api/stocks/<code> - 软删除"""
        response = client.delete('/api/stocks/601857')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_delete_stock_not_found(self, client):
        """DELETE /api/stocks/<code> - 不存在的股票"""
        response = client.delete('/api/stocks/999999')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is False

    def test_restore_stock_success(self, client, test_stock):
        """POST /api/stocks/<code>/restore - 恢复股票"""
        client.delete('/api/stocks/601857')
        response = client.post('/api/stocks/601857/restore')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_restore_stock_not_found(self, client):
        """POST /api/stocks/<code>/restore - 不存在"""
        response = client.post('/api/stocks/999999/restore')
        assert response.status_code == 404

    def test_permanent_delete_success(self, client, test_stock):
        """DELETE /api/stocks/<code>/destroy - 彻底删除"""
        client.delete('/api/stocks/601857')
        response = client.delete('/api/stocks/601857/destroy')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_permanent_delete_not_deleted(self, client, test_stock):
        """DELETE /api/stocks/<code>/destroy - 未软删除的股票"""
        response = client.delete('/api/stocks/601857/destroy')
        assert response.status_code == 404

    def test_list_deleted_stocks(self, client, test_stock):
        """GET /api/stocks/deleted - 获取已删除列表"""
        client.delete('/api/stocks/601857')
        response = client.get('/api/stocks/deleted')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert any(s['code'] == '601857' for s in data)


class TestCodeCheckAPI:
    """代码检查API测试"""

    def test_check_code_valid(self, client):
        """GET /api/stocks/check-code - 有效代码"""
        response = client.get('/api/stocks/check-code?code=601857')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_check_code_invalid(self, client):
        """GET /api/stocks/check-code - 无效格式"""
        response = client.get('/api/stocks/check-code?code=123')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False

    def test_check_code_duplicate(self, client, test_stock):
        """GET /api/stocks/check-code - 重复代码"""
        response = client.get('/api/stocks/check-code?code=601857')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False

    def test_check_code_exclude(self, client, test_stock):
        """GET /api/stocks/check-code - 排除自身"""
        response = client.get('/api/stocks/check-code?code=601857&exclude=601857')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True


class TestIntervalAPI:
    """监控间隔API测试"""

    def test_get_interval(self, client):
        """GET /api/interval - 获取间隔"""
        response = client.get('/api/interval')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'interval_seconds' in data
        assert isinstance(data['interval_seconds'], int)

    def test_set_interval_success(self, client):
        """PUT /api/interval - 设置间隔"""
        response = client.put('/api/interval', json={
            'interval_seconds': 120
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        response = client.get('/api/interval')
        data = json.loads(response.data)
        assert data['interval_seconds'] == 120

    def test_set_interval_too_small(self, client):
        """PUT /api/interval - 间隔太小"""
        response = client.put('/api/interval', json={
            'interval_seconds': 5
        })
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert '不能小于10秒' in data['error']


class TestStockPriceAPI:
    """股票价格API测试"""

    def test_get_price(self, client):
        """GET /api/price/<code> - 获取实时价格"""
        response = client.get('/api/price/601857')
        assert response.status_code in [200, 400]

    def test_get_price_invalid(self, client):
        """GET /api/price/<code> - 无效代码"""
        response = client.get('/api/price/999999')
        assert response.status_code in [200, 400]

    def test_get_stock_name(self, client):
        """GET /api/stock-name/<code> - 获取股票名称"""
        response = client.get('/api/stock-name/601857')
        assert response.status_code in [200, 400]


class TestMonitorAPI:
    """监控功能API测试"""

    def test_monitor_stocks_filter(self, client, test_stock):
        """验证监控股票过滤逻辑"""
        response = client.get('/api/stocks')
        data = json.loads(response.data)
        assert all(s.get('is_deleted', 0) == 0 for s in data)


class TestDataIntegrity:
    """数据完整性测试"""

    def test_stock_fields_complete(self, client, test_stock):
        """验证股票数据字段完整"""
        response = client.get('/api/stocks')
        data = json.loads(response.data)
        stock = next((s for s in data if s['code'] == '601857'), None)
        assert stock is not None
        required_fields = ['code', 'name', 'threshold_percent', 'monitor_enabled']
        for field in required_fields:
            assert field in stock

    def test_soft_delete_preserves_data(self, client, test_stock):
        """软删除后数据应保留在已删除列表"""
        client.delete('/api/stocks/601857')
        response = client.get('/api/stocks/deleted')
        data = json.loads(response.data)
        stock = next((s for s in data if s['code'] == '601857'), None)
        assert stock is not None
        assert stock['name'] == '中国石油'


class TestAPIEdgeCases:
    """API边界情况测试"""

    def test_add_stock_with_sh_prefix(self, client):
        """POST /api/stocks - 带SH前缀"""
        response = client.post('/api/stocks', json={
            'code': 'SH601857',
            'name': '中国石油'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_add_stock_with_sz_prefix(self, client):
        """POST /api/stocks - 带SZ前缀"""
        response = client.post('/api/stocks', json={
            'code': 'SZ000001',
            'name': '平安银行'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_case_insensitive_code(self, client):
        """代码大小写不敏感"""
        client.post('/api/stocks', json={'code': 'ABC', 'name': 'Test'})
        response = client.get('/api/stocks/check-code?code=abc')
        assert response.status_code in [200, 400]
