/**
 * stores/stockStore.js — Pinia 状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '@/api/stocks.js'

export const useStockStore = defineStore('stocks', () => {
  // ── 状态 ───────────────────────────────────────────────
  /** @type {import('vue').Ref<Array>} */
  const stocks = ref([])

  /** @type {import('vue').Ref<Array>} */
  const deletedStocks = ref([])

  /** @type {import('vue').Ref<number>} */
  const intervalSeconds = ref(60)

  /** @type {import('vue').Ref<boolean>} */
  const loading = ref(false)

  // ── 计算属性 ───────────────────────────────────────────
  const deletedCount = computed(() => deletedStocks.value.length)

  // ── Actions ───────────────────────────────────────────

  /**
   * 加载监控列表（含实时价格）
   * @returns {Promise<void>}
   */
  async function loadStocks() {
    loading.value = true
    try {
      stocks.value = await api.getStocks()
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载已删除列表
   * @returns {Promise<void>}
   */
  async function loadDeletedStocks() {
    try {
      deletedStocks.value = await api.getDeletedStocks()
    } catch (e) {
      console.error(e)
    }
  }

  /**
   * 加载全局监控间隔
   * @returns {Promise<void>}
   */
  async function loadInterval() {
    try {
      const data = await api.getInterval()
      intervalSeconds.value = data.interval_seconds || 60
    } catch (e) {
      console.error(e)
    }
  }

  /**
   * 添加股票
   * @param {Object} payload
   * @returns {Promise<{ok: boolean, error?: string}>}
   */
  async function addStock(payload) {
    const result = await api.addStock(payload)
    if (result.ok) await loadStocks()
    return result
  }

  /**
   * 更新股票
   * @param {string} code
   * @param {Object} data
   * @returns {Promise<{ok: boolean, error?: string}>}
   */
  async function updateStock(code, data) {
    const result = await api.updateStock(code, data)
    if (result.ok) await loadStocks()
    return result
  }

  /**
   * 软删除
   * @param {string} code
   * @returns {Promise<{ok: boolean}>}
   */
  async function softDelete(code) {
    const result = await api.deleteStock(code)
    if (result.ok) {
      await loadStocks()
      await loadDeletedStocks()
    }
    return result
  }

  /**
   * 恢复
   * @param {string} code
   * @returns {Promise<{ok: boolean, error?: string}>}
   */
  async function restore(code) {
    const result = await api.restoreStock(code)
    if (result.ok) {
      await loadStocks()
      await loadDeletedStocks()
    }
    return result
  }

  /**
   * 彻底删除
   * @param {string} code
   * @returns {Promise<{ok: boolean, error?: string}>}
   */
  async function destroy(code) {
    const result = await api.destroyStock(code)
    if (result.ok) await loadDeletedStocks()
    return result
  }

  /**
   * 切换监控开关
   * @param {string} code
   * @param {boolean} enabled
   * @returns {Promise<void>}
   */
  async function toggleMonitor(code, enabled) {
    await api.updateStock(code, { monitor_enabled: enabled ? 1 : 0 })
    // 不重新加载整列表，只更新本地状态
    const stock = stocks.value.find(s => s.code === code)
    if (stock) stock.monitor_enabled = enabled ? 1 : 0
  }

  /**
   * 保存全局间隔
   * @param {number} seconds
   * @returns {Promise<{ok: boolean}>}
   */
  async function saveInterval(seconds) {
    const result = await api.setInterval(seconds)
    if (result.ok) intervalSeconds.value = seconds
    return result
  }

  /**
   * 测试通知
   * @returns {Promise<{ok: boolean}>}
   */
  async function testNotify() {
    return api.testNotify()
  }

  /**
   * 校验代码
   * @param {string} code
   * @param {string} [exclude]
   * @returns {Promise<{ok: boolean, error?: string}>}
   */
  async function checkCode(code, exclude) {
    return api.checkCode(code, exclude)
  }

  /**
   * 获取股票名称
   * @param {string} code
   * @returns {Promise<{ok: boolean, name: string}>}
   */
  async function fetchStockName(code) {
    return api.getStockName(code)
  }

  return {
    // state
    stocks,
    deletedStocks,
    intervalSeconds,
    loading,
    // computed
    deletedCount,
    // actions
    loadStocks,
    loadDeletedStocks,
    loadInterval,
    addStock,
    updateStock,
    softDelete,
    restore,
    destroy,
    toggleMonitor,
    saveInterval,
    testNotify,
    checkCode,
    fetchStockName,
  }
})
