#!/usr/bin/env python3
"""
集成测试配置 (tests/conftest.py)
- 测试用数据库隔离
- Flask测试客户端
- 测试数据清理
"""

import os
import sys
import pytest
import tempfile
import shutil

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 测试数据库（临时文件）
TEST_DB_DIR = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(TEST_DB_DIR, 'test_stocks.db')


@pytest.fixture(scope='session', autouse=True)
def setup_test_env():
    """设置测试环境变量"""
    os.environ['STOCK_DB_PATH'] = TEST_DB_PATH
    yield
    # 清理临时数据库
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(scope='function')
def app():
    """创建测试用Flask应用"""
    from app import create_app
    
    # 重置数据库路径
    import models
    models.DB_PATH = TEST_DB_PATH
    models.init_db()
    
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
