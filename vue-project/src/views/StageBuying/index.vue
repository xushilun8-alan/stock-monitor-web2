<template>
  <div class="stage-buying">
    <!-- Header -->
    <header class="sb-header">
      <h2>📉 阶段买入策略跟踪</h2>
      <div class="sb-header-actions">
        <button class="btn btn-outline btn-sm" @click="handleRefresh" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '🔄 刷新价格' }}
        </button>
        <button class="btn btn-outline btn-sm" @click="showRecordModal = true; store.loadRecords()">
          📋 触发记录
        </button>
        <button class="btn btn-outline btn-sm" @click="exportFile">
          📥 导出
        </button>
        <label class="btn btn-outline btn-sm import-btn">
          📤 导入
          <input type="file" accept=".xlsx,.xls" @change="handleImport" style="display:none" />
        </label>
        <button class="btn btn-primary btn-sm" @click="openAddModal">
          + 添加股票
        </button>
      </div>
    </header>

    <!-- 加载状态 -->
    <div v-if="store.loading" class="loading-row">加载中...</div>
    <div v-else-if="store.stocks.length === 0" class="empty-row">
      暂无股票，点击「添加股票」开始
    </div>

    <!-- 股票卡片列表 -->
    <div v-else class="stock-list">
      <div v-for="stock in store.stocks" :key="stock.id" class="stock-card">
        <!-- 卡片头部 -->
        <div class="card-header" @click="toggleCard(stock.id)">
          <div class="card-title">
            <span class="stock-name">{{ stock.price_name || stock.name || stock.code }}</span>
            <span class="stock-code">{{ stock.code }}</span>
          </div>
          <div class="card-meta">
            <span class="current-price" :class="priceClass(stock)">
              {{ stock.current_price != null ? stock.current_price.toFixed(2) : '—' }}
            </span>
            <span v-if="stock.change_percent != null" class="change-pct"
              :class="stock.change_percent >= 0 ? 'up' : 'down'">
              {{ stock.change_percent >= 0 ? '+' : '' }}{{ stock.change_percent.toFixed(2) }}%
            </span>
            <span class="expand-icon" :class="{ open: expandedIds.has(stock.id) }">▼</span>
          </div>
        </div>

        <!-- 简要信息 -->
        <div class="card-brief">
          <div class="brief-item">
            <span class="brief-label">当前阶段</span>
            <span class="brief-value">第{{ stock.current_stage }}/{{ stock.total_stages }}阶段</span>
          </div>
          <div class="brief-item">
            <span class="brief-label">下阶买入价</span>
            <span class="brief-value">{{ stock.next_buy_price != null ? stock.next_buy_price.toFixed(4) : '—' }}</span>
          </div>
          <div class="brief-item">
            <span class="brief-label">距下阶跌幅</span>
            <span class="brief-value" :class="stock.drop_to_next_pct > 0 ? 'down' : 'up'">
              {{ stock.drop_to_next_pct != null ? stock.drop_to_next_pct.toFixed(2) + '%' : '—' }}
            </span>
          </div>
          <div class="brief-item">
            <span class="brief-label">执行进度</span>
            <span class="brief-value">{{ stock.executed_count }}/{{ stock.total_stages }}</span>
          </div>
          <div class="brief-item">
            <span class="brief-label">总买入金额</span>
            <span class="brief-value">{{ formatMoney(stock.total_investment) }}</span>
          </div>
          <div class="brief-item">
            <span class="brief-label">已执行金额</span>
            <span class="brief-value executed">{{ formatMoney(stock.executed_investment) }}</span>
          </div>
          <div class="brief-item">
            <span class="brief-label">盈利亏损比</span>
            <span class="brief-value" :class="stock.profit_loss_ratio != null && stock.profit_loss_ratio < 0 ? 'down' : ''">
              {{ stock.profit_loss_ratio != null ? stock.profit_loss_ratio.toFixed(4) : '—' }}
            </span>
          </div>
          <div class="brief-item">
            <span class="brief-label">收益成本比</span>
            <span class="brief-value">{{ stock.return_cost_ratio != null ? stock.return_cost_ratio.toFixed(2) + '%' : '—' }}</span>
          </div>
        </div>

        <!-- 阶段详情展开 -->
        <div v-if="expandedIds.has(stock.id)" class="card-detail">
          <StageTable
            :stages="stock.stages"
            :current-price="stock.current_price"
            @toggle="handleToggleExec"
            @update-shares="(payload) => handleUpdateShares(stock.id, payload)"
          />
        </div>

        <!-- 卡片底部操作 -->
        <div class="card-actions">
          <button class="btn btn-xs btn-outline" @click="openEditModal(stock)">编辑</button>
          <button class="btn btn-xs btn-danger-outline" @click="confirmDelete(stock)">删除</button>
        </div>
      </div>
    </div>

    <!-- 添加/编辑弹窗 -->
    <StockForm
      :show="showForm"
      :stock="editingStock"
      @close="closeForm"
      @saved="onFormSaved"
    />

    <!-- 删除确认弹窗 -->
    <ConfirmModal
      :show="showDeleteModal"
      title="确认删除"
      :message="deleteMsg"
      confirmText="确认删除"
      @confirm="doDelete"
      @cancel="showDeleteModal = false"
    />

    <!-- 触发记录弹窗 -->
    <TriggerRecord
      :show="showRecordModal"
      :records="store.triggerRecords"
      :filter="store.recordFilter"
      @close="showRecordModal = false"
      @filter-change="handleRecordFilter"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useStageBuyingStore } from './store.js'
import StockForm from './components/StockForm.vue'
import StageTable from './components/StageTable.vue'
import TriggerRecord from './components/TriggerRecord.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import * as api from './api.js'

const store = useStageBuyingStore()

const showForm = ref(false)
const editingStock = ref(null)
const showDeleteModal = ref(false)
const deleteMsg = ref('')
const pendingDeleteId = ref(null)
const showRecordModal = ref(false)
const expandedIds = ref(new Set())
const refreshing = ref(false)

onMounted(() => {
  store.loadStocks()
  store.loadConfig()
})

function toggleCard(id) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

function priceClass(stock) {
  if (stock.change_percent == null) return ''
  return stock.change_percent >= 0 ? 'up' : 'down'
}

function formatMoney(v) {
  if (v == null) return '—'
  return '¥' + v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function openAddModal() {
  editingStock.value = null
  showForm.value = true
}

function openEditModal(stock) {
  editingStock.value = { ...stock }
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingStock.value = null
}

async function onFormSaved() {
  closeForm()
  await store.loadStocks()
}

async function handleToggleExec(stageId) {
  await store.toggleStageExec(stageId)
}

async function handleUpdateShares(stockId, { stageId, shares }) {
  await store.updateStageShares(stageId, shares)
}

function confirmDelete(stock) {
  pendingDeleteId.value = stock.id
  deleteMsg.value = `确定要删除 ${stock.code} ${stock.name || ''} 吗？所有阶段和记录将被删除。`
  showDeleteModal.value = true
}

async function doDelete() {
  if (!pendingDeleteId.value) return
  await store.removeStock(pendingDeleteId.value)
  showDeleteModal.value = false
  pendingDeleteId.value = null
}

async function handleRefresh() {
  refreshing.value = true
  await store.refreshPrices()
  await store.loadStocks()
  refreshing.value = false
}

async function exportFile() {
  const blob = await api.exportStocks()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `stage_buying_${new Date().toISOString().slice(0,10)}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

async function handleImport(e) {
  const file = e.target.files[0]
  if (!file) return
  const res = await api.importStocks(file)
  if (res.ok) {
    alert(`成功导入 ${res.data?.added || 0} 只股票`)
    if (res.data?.errors?.length) {
      alert('部分导入失败: ' + res.data.errors.join('\n'))
    }
    await store.loadStocks()
  } else {
    alert('导入失败: ' + res.error)
  }
  e.target.value = ''
}

function handleRecordFilter(filter) {
  store.recordFilter = { ...filter }
  store.loadRecords()
}
</script>

<style scoped>
.stage-buying {
  padding: 16px;
  max-width: 1200px;
  margin: 0 auto;
}

.sb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.sb-header h2 {
  margin: 0;
  font-size: 18px;
}

.sb-header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.loading-row, .empty-row {
  text-align: center;
  padding: 40px;
  color: #64748b;
}

.stock-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stock-card {
  border: 1px solid #1f2d45;
  border-radius: 8px;
  overflow: hidden;
  background: #111827;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  background: #1a2332;
}

.card-header:hover {
  background: #243044;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stock-name {
  font-weight: 600;
  font-size: 15px;
}

.stock-code {
  color: #64748b;
  font-size: 12px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-price {
  font-weight: 700;
  font-size: 16px;
}

.current-price.up { color: #e53935; }
.current-price.down { color: #43a047; }

.change-pct {
  font-size: 13px;
}
.change-pct.up { color: #e53935; }
.change-pct.down { color: #43a047; }

.expand-icon {
  font-size: 10px;
  color: #64748b;
  transition: transform 0.2s;
}
.expand-icon.open { transform: rotate(180deg); }

.card-brief {
  display: flex;
  flex-wrap: wrap;
  padding: 8px 16px;
  gap: 8px 16px;
  border-top: 1px solid #1f2d45;
}

.brief-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 80px;
}

.brief-label {
  font-size: 11px;
  color: #64748b;
}

.brief-value {
  font-size: 13px;
  font-weight: 500;
}

.brief-value.executed { color: #43a047; }
.brief-value.down { color: #e53935; }
.brief-value.up { color: #43a047; }

.card-detail {
  border-top: 1px solid #1f2d45;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  border-top: 1px solid #1f2d45;
  justify-content: flex-end;
}

/* 通用按钮样式 */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px solid #1f2d45;
  background: #111827;
  color: #f1f5f9;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.btn:hover:not(:disabled) { background: #1a2332; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 5px 10px; font-size: 12px; }
.btn-xs { padding: 3px 8px; font-size: 11px; }
.btn-primary { background: #38bdf8; color: #0a0f1e; border-color: #38bdf8; }
.btn-primary:hover:not(:disabled) { background: #7dd3fc; }
.btn-outline { background: transparent; }
.btn-danger-outline { color: #f43f5e; border-color: #f43f5e; }
.btn-danger-outline:hover { background: rgba(244,63,94,0.15); }

.import-btn { cursor: pointer; }
</style>
