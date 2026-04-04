<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal-header">
          <h3>📋 历史触发记录</h3>
          <button class="close-btn" @click="$emit('close')">×</button>
        </div>

        <div class="modal-body">
          <!-- 筛选 -->
          <div class="filter-bar">
            <div class="filter-item">
              <label>股票代码</label>
              <input v-model="localFilter.code" type="text" placeholder="筛选代码" @change="emitFilter" />
            </div>
            <div class="filter-item">
              <label>开始时间</label>
              <input v-model="localFilter.start_date" type="date" @change="emitFilter" />
            </div>
            <div class="filter-item">
              <label>结束时间</label>
              <input v-model="localFilter.end_date" type="date" @change="emitFilter" />
            </div>
          </div>

          <table class="record-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>股票代码</th>
                <th>股票名称</th>
                <th>触发阶段</th>
                <th>触发价格</th>
                <th>已通知</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in records" :key="r.id">
                <td>{{ formatTime(r.trigger_time) }}</td>
                <td>{{ r.code }}</td>
                <td>{{ r.name }}</td>
                <td>第{{ r.stage_number }}阶段</td>
                <td>{{ r.current_price?.toFixed(4) || '—' }}</td>
                <td>
                  <span class="notif-badge" :class="r.notified ? 'yes' : 'no'">
                    {{ r.notified ? '已通知' : '未通知' }}
                  </span>
                </td>
              </tr>
              <tr v-if="records.length === 0">
                <td colspan="6" class="empty-cell">暂无记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  records: { type: Array, default: () => [] },
  filter: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'filter-change'])

const localFilter = ref({ ...props.filter })

watch(() => props.filter, (v) => {
  localFilter.value = { ...v }
}, { deep: true })

function emitFilter() {
  emit('filter-change', { ...localFilter.value })
}

function formatTime(t) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleString('zh-CN')
  } catch {
    return t
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #111827;
  border-radius: 8px;
  width: 90%;
  max-width: 700px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid #1f2d45;
  flex-shrink: 0;
}

.modal-header h3 { margin: 0; font-size: 15px; color: #f1f5f9; }

.close-btn {
  background: none;
  border: none;
  font-size: 22px;
  cursor: pointer;
  color: #64748b;
}

.modal-body {
  padding: 12px 20px;
  overflow-y: auto;
  flex: 1;
}

.filter-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-item label {
  font-size: 11px;
  color: #94a3b8;
}

.filter-item input {
  padding: 4px 8px;
  border: 1px solid #1f2d45;
  border-radius: 4px;
  font-size: 12px;
  background: #0a0f1e;
  color: #f1f5f9;
}

.record-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.record-table th {
  background: #1a2332;
  padding: 5px 8px;
  text-align: left;
  font-weight: 600;
  color: #94a3b8;
}

.record-table td {
  padding: 5px 8px;
  border-top: 1px solid #1f2d45;
  color: #f1f5f9;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 20px !important;
}

.notif-badge {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
}
.notif-badge.yes { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
.notif-badge.no { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
</style>
