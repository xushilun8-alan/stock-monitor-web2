"""
API 路由层 (routes/__init__.py)

【模块说明】
本包包含所有 Flask Blueprint，用于解耦 app.py 中的路由定义。

【已包含路由】
- stock_api: /api/stocks 系列接口（增删改查 + 恢复/彻底删除）
  挂载点: /api

【未来扩展】
- 如有其他功能模块（如用户管理、设置页等），
  在此包下新建 .py 文件，参照 stock_api.py 格式，
  在 app.py 中通过 register_blueprint 注册。
"""

from routes.stock_api import stock_bp

__all__ = ['stock_bp']
