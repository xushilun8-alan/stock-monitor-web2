/**
 * api/stocks.js — REST API 客户端（与 Flask 后端通信）
 * 所有请求直接发 /api/*（开发环境由 Vite proxy 转发到 :5188）
 */

/**
 * @returns {Promise<Array>}
 */
export async function getStocks() {
  const res = await fetch('/api/stocks')
  if (!res.ok) throw new Error('获取股票列表失败')
  return res.json()
}

/**
 * @param {Object} data
 * @param {string} data.code
 * @param {string} [data.name]
 * @param {number} [data.threshold_percent]
 * @param {number|null} [data.target_price]
 * @param {boolean} [data.rebuy_enabled]
 * @param {string|null} [data.rebuy_date]
 * @param {string} [data.rebuy_time]
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function addStock(data) {
  const res = await fetch('/api/stocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  return res.json()
}

/**
 * @param {string} code
 * @param {Object} data
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function updateStock(code, data) {
  const res = await fetch(`/api/stocks/${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  return res.json()
}

/**
 * 软删除（移入回收站）
 * @param {string} code
 * @returns {Promise<{ok: boolean}>}
 */
export async function deleteStock(code) {
  const res = await fetch(`/api/stocks/${encodeURIComponent(code)}`, { method: 'DELETE' })
  return res.json()
}

/**
 * @returns {Promise<Array>}
 */
export async function getDeletedStocks() {
  const res = await fetch('/api/stocks/deleted')
  if (!res.ok) throw new Error('获取已删除股票失败')
  return res.json()
}

/**
 * @param {string} code
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function restoreStock(code) {
  const res = await fetch(`/api/stocks/${encodeURIComponent(code)}/restore`, { method: 'POST' })
  return res.json()
}

/**
 * 彻底删除（永久移除）
 * @param {string} code
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function destroyStock(code) {
  const res = await fetch(`/api/stocks/${encodeURIComponent(code)}/destroy`, { method: 'DELETE' })
  return res.json()
}

/**
 * @param {string} code
 * @param {string} [exclude]
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function checkCode(code, exclude) {
  const params = new URLSearchParams({ code })
  if (exclude) params.set('exclude', exclude)
  const res = await fetch(`/api/stocks/check-code?${params}`)
  return res.json()
}

/**
 * @param {string} code
 * @returns {Promise<{ok: boolean, name: string}>}
 */
export async function getStockName(code) {
  const res = await fetch(`/api/stock-name/${encodeURIComponent(code)}`)
  return res.json()
}

/**
 * @returns {Promise<{interval_seconds: number}>}
 */
export async function getInterval() {
  const res = await fetch('/api/interval')
  return res.json()
}

/**
 * @param {number} seconds
 * @returns {Promise<{ok: boolean}>}
 */
export async function setInterval(seconds) {
  const res = await fetch('/api/interval', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interval_seconds: seconds })
  })
  return res.json()
}

/**
 * @returns {Promise<{ok: boolean}>}
 */
export async function testNotify() {
  const res = await fetch('/api/test-notify', { method: 'POST' })
  return res.json()
}
