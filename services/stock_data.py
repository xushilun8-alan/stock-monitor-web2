#!/usr/bin/env python3
"""
股价数据获取服务 (services/stock_data.py)

【核心功能】
- get_stock_price(stock_code): 获取单只股票实时价格/涨跌数据
- get_stock_name(code): 获取股票名称（A股/美股通用）
- batch_get_prices(codes): 批量获取多只股票价格

【A股数据源】
1. 腾讯财经 — 优先
2. 新浪财经 — 备用

【美股数据源】
1. Yahoo Finance — 优先（不需要API Key）
2. 新浪国际股 — 备用

【股票分类判断】
- 美股：代码含字母（区分大小写，A-Z） → gb_前缀 + Yahoo/sina国际
- A股：纯数字6位 → sh/sz前缀 + 腾讯/新浪国内

【返回字段】
- current_price: 当前价
- opening_price: 开盘价
- yesterday_close: 昨收价
- high / low: 最高 / 最低价
- change_percent: 涨跌幅百分比 (正=涨, 负=跌)
- update_time: 数据更新时间字符串
- name: 股票名称
- source: 数据来源 (tencent / sina / yahoo)
"""

import requests
import re
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


# ── 价格缓存（内存 TTL）────────────────────────────────────────

class _PriceCache:
    """线程安全的内存价格缓存，TTL 内不重复请求"""
    def __init__(self, ttl_seconds: float = 30):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache.get(code)
            if entry and (time.time() - entry['_ts']) < self._ttl:
                return entry.copy()
        return None

    def set(self, code: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._cache[code] = {**data, '_ts': time.time()}

    def invalidate(self, code: str) -> None:
        with self._lock:
            self._cache.pop(code, None)


_price_cache = _PriceCache(ttl_seconds=30)


# ── 工具函数 ────────────────────────────────────────────────

def is_us_stock(code: str) -> bool:
    """判断是否为美股（代码含字母即为美股）"""
    c = code.lower().replace('gb_', '')
    return bool(re.search(r'[a-z]', c))


def _market_prefix(code: str) -> str:
    """A股：根据代码判断交易所前缀"""
    c = code.lower().replace('sh', '').replace('sz', '')
    if c.startswith(('6', '7', '9', '3')):
        return 'sh'
    return 'sz'


# ── A股 ────────────────────────────────────────────────────

def _get_a_stock_price(code: str) -> Optional[Dict[str, Any]]:
    """
    A股：优先腾讯财经，备用新浪财经
    """
    stock_id = code.lower().replace('sh', '').replace('sz', '')
    prefix = _market_prefix(stock_id)

    # 腾讯财经
    try:
        url = f"http://qt.gtimg.cn/q={prefix}{stock_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and '~' in resp.text:
            data = resp.text.split('~')
            if len(data) > 4:
                current = float(data[3])
                yesterday = float(data[4])
                opening = float(data[5]) if len(data) > 5 and data[5] else current
                change_percent = ((current - yesterday) / yesterday) * 100 if yesterday > 0 else 0
                return {
                    'current_price': current,
                    'opening_price': opening,
                    'yesterday_close': yesterday,
                    'high': float(data[33]) if len(data) > 33 and data[33] else current,
                    'low': float(data[34]) if len(data) > 34 and data[34] else current,
                    'change_percent': change_percent,
                    'update_time': data[30] if len(data) > 30 else datetime.now().strftime('%H:%M:%S'),
                    'name': data[1] if data[1] else code,
                    'source': 'tencent',
                }
    except Exception:
        pass

    # 新浪财经（备用）
    try:
        url = f"https://hq.sinajs.cn/list={prefix}{stock_id}"
        headers = {'Referer': 'https://finance.sina.com.cn'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            content = resp.text
            match = re.search(r'"([^"]*)"', content)
            if match:
                data = match.group(1).split(',')
                if len(data) > 5 and data[1]:
                    current = float(data[3])
                    opening = float(data[1])    # data[1] = 今开
                    yesterday = float(data[2])  # data[2] = 昨收
                    change_percent = ((current - yesterday) / yesterday) * 100 if yesterday > 0 else 0
                    return {
                        'current_price': current,
                        'opening_price': opening,
                        'yesterday_close': yesterday,
                        'high': float(data[4]) if data[4] else current,
                        'low': float(data[5]) if data[5] else current,
                        'change_percent': change_percent,
                        'update_time': datetime.now().strftime('%H:%M:%S'),
                        'name': data[0],
                        'source': 'sina',
                    }
    except Exception:
        pass

    return None


def _get_us_stock_price_yahoo(symbol: str) -> Optional[Dict[str, Any]]:
    """美股：Yahoo Finance（不需要API Key）"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}"
        resp = requests.get(
            url,
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        )
        if resp.status_code != 200:
            return None
        d = resp.json()
        result = d['chart']['result'][0]
        meta = result['meta']

        # 获取昨收价（如果当天未开盘，用前一日收盘价）
        prev_close = meta.get('previousClose', meta.get('chartPreviousClose', 0))
        current = meta.get('regularMarketPrice', 0)
        opening = meta.get('regularMarketOpen', 0)
        high = meta.get('regularMarketDayHigh', 0)
        low = meta.get('regularMarketDayLow', 0)
        timestamp = meta.get('regularMarketTime', 0)

        if opening == 0:
            opening = current

        if prev_close > 0:
            change_percent = ((current - prev_close) / prev_close) * 100
        else:
            change_percent = 0

        return {
            'current_price': current,
            'opening_price': opening,
            'yesterday_close': prev_close,
            'high': high,
            'low': low,
            'change_percent': change_percent,
            'update_time': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else datetime.now().strftime('%H:%M:%S'),
            'name': meta.get('shortName', meta.get('symbol', symbol.upper())),
            'source': 'yahoo',
        }
    except Exception:
        return None


def _get_us_stock_price_sina(symbol: str) -> Optional[Dict[str, Any]]:
    """美股：新浪国际股（备用）"""
    try:
        url = f"https://hq.sinajs.cn/list=gb_{symbol.lower()}"
        headers = {'Referer': 'https://finance.sina.com.cn'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        match = re.search(r'"([^"]*)"', resp.text)
        if not match:
            return None
        data = match.group(1).split(',')
        # data[0]=中文名, data[1]=当前价, data[2]=涨跌额, data[3]=日期时间,
        # data[4]=今开, data[5]=昨收, data[6]=最高, data[7]=最低, ...
        if len(data) < 6:
            return None
        current = float(data[1])
        opening = float(data[4]) if data[4] else current
        yesterday = float(data[5])
        high = float(data[6]) if data[6] else current
        low = float(data[7]) if data[7] else current
        change_percent = (float(data[2]) / yesterday * 100) if yesterday > 0 else 0
        return {
            'current_price': current,
            'opening_price': opening,
            'yesterday_close': yesterday,
            'high': high,
            'low': low,
            'change_percent': change_percent,
            'update_time': data[3] if len(data) > 3 else datetime.now().strftime('%H:%M:%S'),
            'name': data[0],
            'source': 'sina_intl',
        }
    except Exception:
        return None


def _get_us_stock_price(symbol: str) -> Optional[Dict[str, Any]]:
    """美股：Yahoo优先，新浪备用"""
    return _get_us_stock_price_yahoo(symbol) or _get_us_stock_price_sina(symbol)


# ── 公开 API ────────────────────────────────────────────────

def get_stock_price(stock_code: str) -> Optional[Dict[str, Any]]:
    """
    获取单只股票价格数据（A股/美股自动路由）。
    结果会被缓存 30 秒，同一股票 30 秒内的重复调用直接返回缓存值。
    """
    clean = stock_code.strip()
    cached = _price_cache.get(clean)
    if cached:
        return cached
    if is_us_stock(clean):
        data = _get_us_stock_price(clean)
    else:
        data = _get_a_stock_price(clean)
    if data:
        _price_cache.set(clean, data)
    return data


def get_stock_name(code: str) -> str:
    """
    获取股票名称（A股/美股通用）
    A股：通过腾讯数据获取名称
    美股：通过Yahoo Finance获取shortName
    """
    clean = code.strip()
    if is_us_stock(clean):
        sym = clean.upper().replace('GB_', '')
        pd = _get_us_stock_price_yahoo(sym)
        return pd['name'] if pd else ''
    else:
        pd = _get_a_stock_price(clean)
        return pd['name'] if pd else ''


def batch_get_prices(stock_codes: list) -> Dict[str, Optional[Dict]]:
    """
    并行批量获取多只股票价格。
    使用 ThreadPoolExecutor 同时请求所有股票，
    利用缓存保证 30 秒内不重复请求外部 API。
    """
    results = {}
    # 先从缓存读取，剩余的并行抓取
    to_fetch = []
    for code in stock_codes:
        cached = _price_cache.get(code)
        if cached:
            results[code] = cached
        else:
            to_fetch.append(code)

    if not to_fetch:
        return results

    def _fetch(code: str) -> tuple:
        data = get_stock_price(code)  # 会走缓存逻辑
        return (code, data)

    with ThreadPoolExecutor(max_workers=min(len(to_fetch), 10)) as executor:
        futures = {executor.submit(_fetch, c): c for c in to_fetch}
        for future in as_completed(futures):
            try:
                code, data = future.result()
                results[code] = data
            except Exception:
                pass
    return results
