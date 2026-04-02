#!/usr/bin/env python3
"""
股票监控系统启动入口 (run.py)

【用法】
    python run.py

【说明】
- 启动 Flask 开发服务器（host=0.0.0.0, port=5188, debug=True）
- 自动启动后台监控线程
- 访问 http://localhost:5188 查看监控主页
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app

if __name__ == '__main__':
    print("=" * 50)
    print("📊 股票监控系统已启动")
    print("   主页: http://localhost:5188")
    print("   已删除股票管理: http://localhost:5188/deleted")
    print("   API 文档: 见 routes/stock_api.py")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5188, debug=True)
