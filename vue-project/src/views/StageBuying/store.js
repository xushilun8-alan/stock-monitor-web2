import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from './api.js'

export const useStageBuyingStore = defineStore('stageBuying', () => {
  // 状态
  const stocks = ref([])
  const loading = ref(false)
  const error = ref(null)
  const config = ref({ feishu_enabled: true })

  // 触发记录弹窗
  const showRecordModal = ref(false)
  const triggerRecords = ref([])
  const recordFilter = ref({ code: '', start_date: '', end_date: '' })

  // 计算属性
  const stockCount = computed(() => stocks.value.length)

  // 动作
  async function loadStocks() {
    loading.value = true
    error.value = null
    try {
      const res = await api.getStocks()
      stocks.value = res.ok ? res.data : []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function addStock(data) {
    const res = await api.addStock(data)
    if (res.ok) {
      await loadStocks()
    }
    return res
  }

  async function updateStock(id, data) {
    const res = await api.updateStock(id, data)
    if (res.ok) {
      await loadStocks()
    }
    return res
  }

  async function removeStock(id) {
    const res = await api.deleteStock(id)
    if (res.ok) {
      await loadStocks()
    }
    return res
  }

  async function refreshPrices() {
    return api.refreshPrices()
  }

  async function toggleStageExec(stageId) {
    const res = await api.toggleStageExec(stageId)
    if (res.ok) {
      await loadStocks()
    }
    return res
  }

  async function loadRecords() {
    const res = await api.getTriggerRecords(recordFilter.value)
    if (res.ok) {
      triggerRecords.value = res.data || []
    }
    return res
  }

  async function loadConfig() {
    const res = await api.getConfig()
    if (res.ok) {
      config.value = res.data || {}
    }
  }

  async function saveConfig(data) {
    const res = await api.updateConfig(data)
    if (res.ok) {
      config.value = { ...config.value, ...data }
    }
    return res
  }

  async function testFeishu() {
    return api.testFeishu()
  }

  return {
    stocks, loading, error, config,
    showRecordModal, triggerRecords, recordFilter,
    stockCount,
    loadStocks, addStock, updateStock, removeStock,
    refreshPrices, toggleStageExec,
    loadRecords, loadConfig, saveConfig, testFeishu,
  }
})
