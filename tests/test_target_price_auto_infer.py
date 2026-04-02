#!/usr/bin/env python3
"""
目标价自动推断功能测试
- 使用隔离的测试数据库
- 测试完成后自动删除测试库
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 测试数据库路径
TEST_DB_DIR = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(TEST_DB_DIR, 'test_target_price.db')

print(f"测试数据库: {TEST_DB_PATH}")

try:
    # 替换生产数据库路径
    import models
    original_db_path = models.DB_PATH
    models.DB_PATH = TEST_DB_PATH
    
    # 初始化测试数据库
    models.init_db()
    
    # Mock飞书通知
    from services import feishu_notifier
    original_send_alert = feishu_notifier.send_alert
    alert_history = []
    
    def mock_send_alert(**kwargs):
        alert_history.append(kwargs)
        print(f"  [Mock告警] {kwargs.get('stock_code')} - {kwargs.get('reason')}")
        return True
    
    # 先patch feishu_notifier
    feishu_notifier.send_alert = mock_send_alert
    
    # 导入监控模块（通过命名空间访问，避免闭包问题）
    import services.monitor as monitor_module
    monitor_module.send_alert = mock_send_alert
    
    # 获取函数引用
    check_and_notify = monitor_module.check_and_notify
    
    def reset_and_clear():
        """重置通知缓存并清空历史"""
        monitor_module._reset_daily_cache()
        # 手动清空_notified_today，因为_reset_daily_cache只在新日期时清空
        monitor_module._notified_today.clear()
        alert_history.clear()
    
    print("\n" + "="*60)
    print("测试1: 当前价 > 目标价 → 止盈监控（涨破触发）")
    print("="*60)
    
    reset_and_clear()
    
    # 场景: 目标价7.0，当前价8.0（价格已在目标价上方）
    price_data = {
        'current_price': 8.0,
        'change_percent': 5.0,
        'opening_price': 7.6,
        'high': 8.1,
        'low': 7.5
    }
    
    check_and_notify(
        code='601857',
        name='中国石油',
        threshold_percent=2.0,
        target_price=7.0,
        price_data=price_data
    )
    
    assert len(alert_history) == 1, f"预期触发1次告警，实际{len(alert_history)}次"
    assert "止盈监控" in alert_history[0]['reason'], f"告警原因不符: {alert_history[0]['reason']}"
    print("✅ 测试1通过: 价格8.0 > 目标价7.0，触发止盈监控\n")
    
    print("="*60)
    print("测试2: 当前价 < 目标价 → 买入监控（跌到触发）")
    print("="*60)
    
    reset_and_clear()
    
    # 场景: 目标价7.0，当前价6.0（价格低于目标价）
    price_data = {
        'current_price': 6.0,
        'change_percent': -5.0,
        'opening_price': 6.3,
        'high': 6.5,
        'low': 5.9
    }
    
    check_and_notify(
        code='601857',
        name='中国石油',
        threshold_percent=2.0,
        target_price=7.0,
        price_data=price_data
    )
    
    assert len(alert_history) == 1, f"预期触发1次告警，实际{len(alert_history)}次"
    assert "买入监控" in alert_history[0]['reason'], f"告警原因不符: {alert_history[0]['reason']}"
    print("✅ 测试2通过: 价格6.0 < 目标价7.0，触发买入监控\n")
    
    print("="*60)
    print("测试3: 当前价 = 目标价 → 止盈监控（边界值）")
    print("="*60)
    
    reset_and_clear()
    
    price_data = {
        'current_price': 7.0,
        'change_percent': 0.0,
        'opening_price': 7.0,
        'high': 7.1,
        'low': 6.9
    }
    
    check_and_notify(
        code='601857',
        name='中国石油',
        threshold_percent=2.0,
        target_price=7.0,
        price_data=price_data
    )
    
    assert len(alert_history) == 1, f"预期触发1次告警，实际{len(alert_history)}次"
    assert "止盈监控" in alert_history[0]['reason'], f"告警原因不符: {alert_history[0]['reason']}"
    print("✅ 测试3通过: 价格7.0 = 目标价7.0，触发止盈监控\n")
    
    print("="*60)
    print("测试4: 无目标价时，仅触发涨跌告警")
    print("="*60)
    
    reset_and_clear()
    
    price_data = {
        'current_price': 6.0,
        'change_percent': -5.0,
        'opening_price': 6.3,
        'high': 6.5,
        'low': 5.9
    }
    
    # threshold_percent=-5.0（负值监控跌幅），change=-5% → 触发跌幅告警
    check_and_notify(
        code='601857',
        name='中国石油',
        threshold_percent=-5.0,  # 负阈值，监控跌幅
        target_price=None,  # 无目标价
        price_data=price_data
    )
    
    assert len(alert_history) == 1, f"预期触发1次告警，实际{len(alert_history)}次"
    assert "跌幅" in alert_history[0]['reason'], f"告警原因不符: {alert_history[0]['reason']}"
    print("✅ 测试4通过: 无目标价时触发涨跌告警\n")
    
    print("="*60)
    print("测试5: 回归测试 - 原涨跌幅阈值逻辑不受影响")
    print("="*60)
    
    reset_and_clear()
    
    # 正阈值：涨幅达标
    price_data = {
        'current_price': 7.5,
        'change_percent': 3.0,
        'opening_price': 7.3,
        'high': 7.6,
        'low': 7.2
    }
    
    check_and_notify(
        code='601857',
        name='中国石油',
        threshold_percent=2.0,
        target_price=None,
        price_data=price_data
    )
    
    assert len(alert_history) == 1, f"预期触发1次告警，实际{len(alert_history)}次"
    assert "涨幅" in alert_history[0]['reason'], f"应为涨幅告警: {alert_history[0]['reason']}"
    print("✅ 测试5通过: 涨幅3% > 阈值2%，触发涨幅告警\n")
    
    print("="*60)
    print("测试6: 负阈值跌幅告警不受影响")
    print("="*60)
    
    reset_and_clear()
    
    # 负阈值：跌至-5%
    price_data = {
        'current_price': 6.5,
        'change_percent': -5.0,
        'opening_price': 6.8,
        'high': 6.9,
        'low': 6.4
    }
    
    check_and_notify(
        code='601857',
        name='中国石油',
        threshold_percent=-5.0,  # 负阈值
        target_price=None,
        price_data=price_data
    )
    
    assert len(alert_history) == 1, f"预期触发1次告警，实际{len(alert_history)}次"
    assert "跌幅" in alert_history[0]['reason'], f"应为跌幅告警: {alert_history[0]['reason']}"
    print("✅ 测试6通过: 负阈值-5%，跌幅-5%达标\n")
    
    print("="*60)
    print("🎉 全部测试通过!")
    print("="*60)

finally:
    # 恢复原始配置
    models.DB_PATH = original_db_path
    feishu_notifier.send_alert = original_send_alert
    
    # 删除测试数据库
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)
    print(f"\n🧹 测试数据库已清理: {TEST_DB_DIR}")
