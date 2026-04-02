#!/usr/bin/env python3
"""
目标价方向字段功能测试（方案A）
测试显式target_price_direction字段
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TEST_DB_DIR = tempfile.mkdtemp()
TEST_DB_PATH = os.path.join(TEST_DB_DIR, 'test_target_price.db')

print(f"测试数据库: {TEST_DB_PATH}")

try:
    import models
    original_db_path = models.DB_PATH
    models.DB_PATH = TEST_DB_PATH
    models.init_db()
    
    from services import feishu_notifier
    original_send_alert = feishu_notifier.send_alert
    alert_history = []
    
    def mock_send_alert(**kwargs):
        alert_history.append(kwargs)
        print(f"  [Mock告警] {kwargs.get('reason')}")
        return True
    
    feishu_notifier.send_alert = mock_send_alert
    
    import services.monitor as monitor_module
    monitor_module.send_alert = mock_send_alert
    
    check_and_notify = monitor_module.check_and_notify
    
    def reset_and_clear():
        monitor_module._reset_daily_cache()
        monitor_module._notified_today.clear()
        alert_history.clear()
    
    # ========== 场景A: 止盈监控测试 ==========
    print("\n" + "="*60)
    print("【止盈监控测试】(direction=1)")
    print("="*60)
    
    print("\n测试A1: 止盈监控 - 仅目标价触发（涨跌未达阈值）")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', 5.0, 7.0, 1, {
        'current_price': 7.5, 'change_percent': 1.0,
        'opening_price': 7.4, 'high': 7.6, 'low': 7.3
    })
    
    assert len(alert_history) == 1, f"预期1次，实际{len(alert_history)}"
    assert "止盈监控" in alert_history[0]['reason'], f"应为止盈监控: {alert_history[0]['reason']}"
    print("✅ 通过\n")
    
    print("\n测试A2: 止盈监控 - 涨跌+目标价同时触发（验证key隔离）")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', 2.0, 7.0, 1, {
        'current_price': 7.5, 'change_percent': 4.0,
        'opening_price': 7.2, 'high': 7.6, 'low': 7.1
    })
    
    assert len(alert_history) == 2, f"预期2次（涨跌+止盈），实际{len(alert_history)}"
    reasons = [a['reason'] for a in alert_history]
    assert any("涨幅" in r for r in reasons), f"缺少涨跌告警: {reasons}"
    assert any("止盈监控" in r for r in reasons), f"缺少止盈告警: {reasons}"
    print("✅ 通过\n")
    
    print("\n测试A3: 止盈监控 - 价格未达时无目标价告警")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', 2.0, 8.0, 1, {
        'current_price': 7.5, 'change_percent': 2.0,
        'opening_price': 7.3, 'high': 7.6, 'low': 7.2
    })
    
    assert len(alert_history) == 1
    assert "涨幅" in alert_history[0]['reason']
    assert not any("止盈" in a['reason'] for a in alert_history)
    print("✅ 通过\n")
    
    # ========== 场景B: 买入监控测试 ==========
    print("="*60)
    print("【买入监控测试】(direction=-1)")
    print("="*60)
    
    print("\n测试B1: 买入监控 - 价格跌至目标")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', 2.0, 6.0, -1, {
        'current_price': 5.8, 'change_percent': 1.0,
        'opening_price': 5.7, 'high': 5.9, 'low': 5.7
    })
    
    assert len(alert_history) == 1, f"预期1次，实际{len(alert_history)}"
    assert "买入监控" in alert_history[0]['reason'], f"应为买入监控: {alert_history[0]['reason']}"
    print("✅ 通过\n")
    
    print("\n测试B2: 买入监控 - 跌幅告警也触发")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', -3.0, 6.0, -1, {
        'current_price': 5.7, 'change_percent': -3.5,
        'opening_price': 5.9, 'high': 6.0, 'low': 5.6
    })
    
    assert len(alert_history) == 2, f"预期2次（跌幅+买入），实际{len(alert_history)}"
    reasons = [a['reason'] for a in alert_history]
    assert any("跌幅" in r for r in reasons), f"缺少跌幅告警: {reasons}"
    assert any("买入监控" in r for r in reasons), f"缺少买入告警: {reasons}"
    print("✅ 通过\n")
    
    print("\n测试B3: 买入监控 - 价格未到时无目标价告警（但有涨幅告警）")
    reset_and_clear()
    
    # direction=-1(买入), current=5.5 > target=5.0 → 不触发买入
    # threshold=2.0, change=2.5 >= 2.0 → 触发涨幅
    check_and_notify('601857', '中国石油', 2.0, 5.0, -1, {
        'current_price': 5.5, 'change_percent': 2.5,
        'opening_price': 5.4, 'high': 5.6, 'low': 5.3
    })
    
    assert len(alert_history) == 1, f"预期1次涨幅告警，实际{len(alert_history)}"
    assert not any("买入" in a['reason'] for a in alert_history)
    assert any("涨幅" in a['reason'] for a in alert_history)
    print("✅ 通过\n")
    
    # ========== 场景C: 回归测试 ==========
    print("="*60)
    print("【回归测试】")
    print("="*60)
    
    print("\n测试C1: 无目标价，仅涨跌告警")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', 3.0, None, 1, {
        'current_price': 7.5, 'change_percent': 4.0,
        'opening_price': 7.2, 'high': 7.6, 'low': 7.1
    })
    
    assert len(alert_history) == 1
    assert "涨幅" in alert_history[0]['reason']
    print("✅ 通过\n")
    
    print("\n测试C2: 同日重复触发应被拦截")
    reset_and_clear()
    
    check_and_notify('601857', '中国石油', 2.0, 7.0, 1, {
        'current_price': 7.5, 'change_percent': 4.0,
        'opening_price': 7.2, 'high': 7.6, 'low': 7.1
    })
    assert len(alert_history) == 2
    alert_history.clear()
    
    check_and_notify('601857', '中国石油', 2.0, 7.0, 1, {
        'current_price': 7.6, 'change_percent': 3.0,
        'opening_price': 7.4, 'high': 7.7, 'low': 7.3
    })
    assert len(alert_history) == 0, f"重复触发应被拦截，实际{len(alert_history)}"
    print("✅ 通过\n")
    
    print("="*60)
    print("🎉 全部测试通过!")
    print("="*60)
    print("\n验证结果:")
    print("- target_price_direction=1: 止盈监控(涨破触发)")
    print("- target_price_direction=-1: 买入监控(跌到触发)")
    print("- 两种告警独立判断、独立发送、独立去重")

finally:
    models.DB_PATH = original_db_path
    feishu_notifier.send_alert = original_send_alert
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)
    print(f"\n🧹 测试数据库已清理")
