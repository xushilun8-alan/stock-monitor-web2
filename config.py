"""
配置文件 (config.py)

【飞书配置】
- FEISHU_APP_ID / FEISHU_APP_SECRET: 应用凭证，用于获取 tenant_access_token
- FEISHU_RECEIVE_ID: 接收消息用户的 open_id / user_id / union_id
- FEISHU_RECEIVE_ID_TYPE: 接收者 ID 类型（open_id / user_id / union_id / email / phone_number / chat_id）
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """应用配置"""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///data/stocks.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Feishu 飞书开放平台应用凭证
    FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', 'cli_a958dcb710389bb6')
    FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', '0gLEeFXtNrtJuoK2zf9wjbaVCaL2BRgm')

    # 飞书消息接收者
    FEISHU_RECEIVE_ID = os.getenv('FEISHU_RECEIVE_ID', 'b8583212')
    FEISHU_RECEIVE_ID_TYPE = os.getenv('FEISHU_RECEIVE_ID_TYPE', 'user_id')

    # 监控检查间隔（秒）
    MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL', '60'))

    # 日志
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
