#!/usr/bin/env python3
"""
验收测试：涨跌幅阈值双值解析与校验
2026-04-08

运行方式：
    cd /Users/xusl/openclaw_projects/stock-monitor-web2
    python3 tests/test_threshold.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import validate_threshold, parse_threshold


def eq(got, expected, msg=""):
    status = "✅" if got == expected else "❌"
    print(f"  {status} {msg} → expected={expected!r}, got={got!r}")
    return got == expected


def run_all():
    print("\n" + "="*60)
    print("验收测试：涨跌幅阈值双值解析与校验")
    print("="*60)

    all_pass = True

    # ── validate_threshold ─────────────────────────────────────
    print("\n【validate_threshold】")

    # 空值
    all_pass &= eq(validate_threshold(""), "")
    all_pass &= eq(validate_threshold(None), "")
    all_pass &= eq(validate_threshold("  "), "")

    # 单值
    all_pass &= eq(validate_threshold("5"), "5")
    all_pass &= eq(validate_threshold("2.5"), "2.5")
    all_pass &= eq(validate_threshold("-3"), "-3")
    all_pass &= eq(validate_threshold("-2.5"), "-2.5")
    all_pass &= eq(validate_threshold("  5  "), "5")
    all_pass &= eq(validate_threshold("0"), "")       # 0 不监控

    # 双值（规范排序）
    all_pass &= eq(validate_threshold("5 -3"), "5 -3")
    all_pass &= eq(validate_threshold("-3 5"), "5 -3")   # 自动排序
    all_pass &= eq(validate_threshold("2.5 -1.5"), "2.5 -1.5")

    # 非法
    all_pass &= eq(validate_threshold("2 3"), "")         # 同正
    all_pass &= eq(validate_threshold("-4 -2"), "")       # 同负
    all_pass &= eq(validate_threshold("5 a"), "")        # 含字母
    all_pass &= eq(validate_threshold("abc"), "")         # 纯字母
    all_pass &= eq(validate_threshold("5% -3"), "")       # 含符号
    all_pass &= eq(validate_threshold("3 -2 4"), "")     # 3个值

    # ── parse_threshold ────────────────────────────────────────
    print("\n【parse_threshold】")

    all_pass &= eq(parse_threshold(""), (None, None))
    all_pass &= eq(parse_threshold(None), (None, None))
    all_pass &= eq(parse_threshold("5"), (5.0, None))
    all_pass &= eq(parse_threshold("2.5"), (2.5, None))
    all_pass &= eq(parse_threshold("-3"), (None, -3.0))
    all_pass &= eq(parse_threshold("-2.5"), (None, -2.5))
    all_pass &= eq(parse_threshold("5 -3"), (5.0, -3.0))
    all_pass &= eq(parse_threshold("-3 5"), (5.0, -3.0))
    all_pass &= eq(parse_threshold("-2 8"), (8.0, -2.0))
    all_pass &= eq(parse_threshold("abc"), (None, None))

    # ── 组合闭环 ───────────────────────────────────────────────
    print("\n【组合闭环】")
    for raw in ["", "5", "-3", "5 -3", "-3 5", "2.5 -1.5"]:
        validated = validate_threshold(raw)
        rise, fall = parse_threshold(validated)
        print(f"  {raw!r:12s} → validate={validated!r:12s} → rise={rise}, fall={fall}")

    # ── check_and_notify ───────────────────────────────────────
    print("\n【check_and_notify 逻辑模拟】")
    import services.monitor as mon
    from unittest.mock import patch

    # 捕获发送记录
    sent = []

    def mock_send_alert(**kwargs):
        sent.append(kwargs)

    # patch 到 monitor 模块的命名空间（send_alert 在 monitor.py 中 from 进来）
    with patch.object(mon, 'send_alert', mock_send_alert):
        # 重置全局状态
        mon._notified_today = set()
        mon._last_notif_date = ""

        # Case 1: 空值 → 不触发
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T1", "股", rise_threshold=None, fall_threshold=None,
                             price_data={'change_percent': 6.0, 'current_price': 10.6})
        all_pass &= eq(len(sent), 0, "空值不触发")
        print(f"  Case1 空值: sent={len(sent)} ✅" if len(sent) == 0 else f"  Case1 ❌ sent={sent}")

        # Case 2: 涨幅阈值触发
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T2", "股", rise_threshold=5.0, fall_threshold=None,
                             price_data={'change_percent': 6.0, 'current_price': 10.6})
        all_pass &= eq(len(sent), 1, "单值涨幅6%≥5% → 触发1次")
        all_pass &= eq("上涨" in sent[0]['reason'], True, "上涨告警理由正确")
        print(f"  Case2 涨幅: sent={[(s['reason'],) for s in sent]}")

        # Case 3: 跌幅阈值触发
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T3", "股", rise_threshold=None, fall_threshold=-3.0,
                             price_data={'change_percent': -5.0, 'current_price': 9.5})
        all_pass &= eq(len(sent), 1, "单值跌幅-5%≤-3% → 触发1次")
        all_pass &= eq("下跌" in sent[0]['reason'], True, "下跌告警理由正确")
        print(f"  Case3 跌幅: sent={[(s['reason'],) for s in sent]}")

        # Case 4: 双值，涨超涨阈
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T4", "股", rise_threshold=5.0, fall_threshold=-3.0,
                             price_data={'change_percent': 6.0, 'current_price': 10.6})
        all_pass &= eq(len(sent), 1, "双值涨6%≥5%，跌-2%未达-3% → 触发1次")
        all_pass &= eq("上涨" in sent[0]['reason'], True, "上涨告警")
        print(f"  Case4 双值涨: sent={[(s['reason'],) for s in sent]}")

        # Case 5: 双值，跌超跌阈
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T5", "股", rise_threshold=5.0, fall_threshold=-3.0,
                             price_data={'change_percent': -4.0, 'current_price': 9.6})
        all_pass &= eq(len(sent), 1, "双值跌-4%≤-3%，涨2%未达5% → 触发1次")
        all_pass &= eq("下跌" in sent[0]['reason'], True, "下跌告警")
        print(f"  Case5 双值跌: sent={[(s['reason'],) for s in sent]}")

        # Case 6: 双值，同时触发
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T6", "股", rise_threshold=3.0, fall_threshold=-3.0,
                             price_data={'change_percent': -5.0, 'current_price': 9.5})
        all_pass &= eq(len(sent), 1, "双值跌-5%≤-3% → 触发下跌（涨-5%<3%不触发）")
        all_pass &= eq("下跌" in sent[0]['reason'], True, "下跌告警")
        print(f"  Case6 双值同时: sent={[(s['reason'],) for s in sent]}")

        # Case 7: 未达阈值不触发
        sent.clear()
        mon._notified_today = set()
        mon._last_notif_date = ""
        mon.check_and_notify("T7", "股", rise_threshold=5.0, fall_threshold=-3.0,
                             price_data={'change_percent': 2.0, 'current_price': 10.2})
        all_pass &= eq(len(sent), 0, "涨幅2%<5%，跌幅-2%>-3% → 均不触发")
        print(f"  Case7 不触发: sent={len(sent)} ✅" if len(sent) == 0 else f"  Case7 ❌ sent={sent}")

    # ── 总结 ───────────────────────────────────────────────────
    print("\n" + "="*60)
    print(f"结果：{'✅ 全部通过' if all_pass else '❌ 存在失败项'}")
    print("="*60)
    return all_pass


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
