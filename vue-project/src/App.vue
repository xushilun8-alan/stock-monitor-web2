<template>
  <div class="container">
    <!-- Header -->
    <header class="app-header">
      <h1>📊 股票监控系统</h1>
      <div class="header-actions">
        <div class="status-indicator">
          <span class="status-dot"></span>
          监控运行中
        </div>
        <button class="btn btn-outline btn-sm" @click="handleTestNotify">
          测试飞书通知
        </button>
        <button class="btn btn-primary btn-sm" @click="openAddModal">
          + 添加股票
        </button>
      </div>
    </header>

    <!-- 导航 -->
    <NavTabs
      :activeTab="activeTab"
      :deletedCount="store.deletedCount"
      @change="onTabChange"
    />

    <!-- 全局间隔设置 -->
    <IntervalBar :interval="store.intervalSeconds" />

    <!-- 回收站计数提示（仅监控列表页） -->
    <div class="deleted-banner" :class="{ hidden: store.deletedCount === 0 || activeTab !== 'monitor' }">
      <span>⚠️</span>
      <span>
        有 <strong>{{ store.deletedCount }}</strong> 只已删除股票，
        <a href="#" @click.prevent="onTabChange('deleted')">查看并管理</a>
      </span>
    </div>

    <!-- 监控列表 -->
    <StockTable
      v-if="activeTab === 'monitor'"
      :stocks="store.stocks"
      @add="openAddModal"
      @edit="openEditModal"
      @delete="openDeleteConfirm"
    />

    <!-- 阶段买入策略 -->
    <StageBuyingView v-if="activeTab === 'stage-buying'" />

    <!-- 回收站 -->
    <DeletedTable
      v-if="activeTab === 'deleted'"
      :stocks="store.deletedStocks"
      @restore="handleRestore"
      @destroy="openDestroyConfirm"
    />

    <!-- 添加/编辑弹窗 -->
    <StockModal
      :show="showStockModal"
      :editStock="editingStock"
      @close="closeStockModal"
      @saved="onStockSaved"
    />

    <!-- 删除确认弹窗 -->
    <ConfirmModal
      :show="showDeleteModal"
      title="确认删除"
      :message="deleteModalMsg"
      confirmText="确认删除"
      @confirm="confirmDelete"
      @cancel="showDeleteModal = false"
    />

    <!-- 彻底删除确认弹窗 -->
    <DestroyModal
      :show="showDestroyModal"
      :message="destroyModalMsg"
      @confirm="confirmDestroy"
      @cancel="showDestroyModal = false"
    />

    <!-- Toast -->
    <ToastNotification />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useStockStore } from '@/stores/stockStore.js'
import { useToast } from '@/composables/useToast.js'

import NavTabs from '@/components/NavTabs.vue'
import IntervalBar from '@/components/IntervalBar.vue'
import StockTable from '@/components/StockTable.vue'
import DeletedTable from '@/components/DeletedTable.vue'
import StockModal from '@/components/StockModal.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import DestroyModal from '@/components/DestroyModal.vue'
import ToastNotification from '@/components/ToastNotification.vue'
import StageBuyingView from '@/views/StageBuying/index.vue'

// ── Store ───────────────────────────────────────────────
const store = useStockStore()
const { toast } = useToast()

// ── Tab 状态 ─────────────────────────────────────────────
/** @type {import('vue').Ref<'monitor'|'stage-buying'|'deleted'>} */
const activeTab = ref('monitor')

// ── 弹窗状态 ─────────────────────────────────────────────
/** @type {import('vue').Ref<boolean>} */
const showStockModal = ref(false)

/** @type {import('vue').Ref<Object|null>} */
const editingStock = ref(null)

/** @type {import('vue').Ref<boolean>} */
const showDeleteModal = ref(false)
/** @type {import('vue').Ref<string>} */
const deleteModalMsg = ref('')

/** @type {import('vue').Ref<boolean>} */
const showDestroyModal = ref(false)
/** @type {import('vue').Ref<string>} */
const destroyModalMsg = ref('')

/** @type {import('vue').Ref<string|null>} */
const pendingDeleteCode = ref(null)
/** @type {import('vue').Ref<string|null>} */
const pendingDestroyCode = ref(null)

// ── Auto-refresh ─────────────────────────────────────────
/** @type {number|null} */
let refreshTimer = null

function startRefresh() {
  stopRefresh()
  refreshTimer = setInterval(() => {
    if (activeTab.value === 'monitor') store.loadStocks()
  }, 30000)
}

function stopRefresh() {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// ── Tab 切换 ─────────────────────────────────────────────
async function onTabChange(tab) {
  activeTab.value = tab
  if (tab === 'monitor') {
    await store.loadStocks()
    startRefresh()
  } else {
    await store.loadDeletedStocks()
    stopRefresh()
  }
}

// ── 初始化 ───────────────────────────────────────────────
onMounted(async () => {
  await store.loadInterval()
  await store.loadDeletedStocks()
  await store.loadStocks()
  startRefresh()
})

onUnmounted(() => stopRefresh())

// ── 添加股票 ─────────────────────────────────────────────
function openAddModal() {
  editingStock.value = null
  showStockModal.value = true
}

function closeStockModal() {
  showStockModal.value = false
  editingStock.value = null
}

// ── 编辑股票 ─────────────────────────────────────────────
/**
 * @param {Object} stock
 */
function openEditModal(stock) {
  editingStock.value = { ...stock }
  showStockModal.value = true
}

function onStockSaved() {
  // store already reloaded
}

// ── 删除（软删除）────────────────────────────────────────
/**
 * @param {Object} stock
 */
function openDeleteConfirm(stock) {
  pendingDeleteCode.value = stock.code
  deleteModalMsg.value =
    `确定要将 ${stock.code.toUpperCase()} ${stock.name ? stock.name : ''} 移入回收站吗？删除后可随时恢复。`
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!pendingDeleteCode.value) return
  const result = await store.softDelete(pendingDeleteCode.value)
  if (result.ok) {
    toast('已移入回收站', 'ok')
  } else {
    toast('删除失败', 'err')
  }
  showDeleteModal.value = false
  pendingDeleteCode.value = null
}

// ── 恢复 ─────────────────────────────────────────────────
/**
 * @param {Object} stock
 */
async function handleRestore(stock) {
  const result = await store.restore(stock.code)
  if (result.ok) {
    toast('已恢复', 'ok')
    await store.loadDeletedStocks()
  } else {
    toast(result.error || '恢复失败', 'err')
  }
}

// ── 彻底删除 ─────────────────────────────────────────────
/**
 * @param {Object} stock
 */
function openDestroyConfirm(stock) {
  pendingDestroyCode.value = stock.code
  destroyModalMsg.value =
    `确定要永久删除 ${stock.code.toUpperCase()} ${stock.name ? stock.name : ''} 吗？此操作不可恢复。`
  showDestroyModal.value = true
}

async function confirmDestroy() {
  if (!pendingDestroyCode.value) return
  const result = await store.destroy(pendingDestroyCode.value)
  if (result.ok) {
    toast('已彻底删除', 'ok')
  } else {
    toast(result.error || '彻底删除失败', 'err')
  }
  showDestroyModal.value = false
  pendingDestroyCode.value = null
}

// ── 测试通知 ─────────────────────────────────────────────
async function handleTestNotify() {
  const result = await store.testNotify()
  toast(result.ok ? '测试通知已发送，请查收飞书' : '发送失败', result.ok ? 'ok' : 'err')
}
</script>
