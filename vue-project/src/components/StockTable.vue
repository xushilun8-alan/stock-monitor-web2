<template>
  <div class="table-card">
    <table>
      <thead>
        <tr>
          <th>股票代码</th>
          <th>股票名称</th>
          <th>现价</th>
          <th>涨跌幅阈值</th>
          <th>目标价</th>
          <th>重新买进提醒</th>
          <th>监控</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="stocks.length === 0">
          <td colspan="8">
            <div class="empty-state">
              <p>暂无监控股票</p>
              <button class="btn btn-primary" @click="$emit('add')">+ 添加第一只股票</button>
            </div>
          </td>
        </tr>
        <tr v-for="s in stocks" :key="s.code">
          <td><strong style="font-size:0.9rem">{{ s.code.toUpperCase() }}</strong></td>
          <td>
            <span v-if="s.name || s.price_name" style="color:var(--accent)">
              {{ s.name || s.price_name }}
            </span>
            <span v-else style="color:var(--muted)">—</span>
          </td>
          <td>
            <div class="price-wrap">
              <span v-if="s.current_price != null" class="price-main" :class="priceClass(s)">
                {{ s.current_price.toFixed(2) }}
                <span class="price-change" :class="priceClass(s)">
                  {{ s.change_percent >= 0 ? '+' : '' }}{{ s.change_percent?.toFixed(2) }}%
                </span>
              </span>
              <span v-else class="price-main null">暂无数据</span>
              <div v-if="s.update_time" class="update-time">{{ s.update_time }}</div>
            </div>
          </td>
          <td>
            <span class="threshold">
              {{ s.threshold_percent > 0 ? '涨' : '跌' }}{{ Math.abs(s.threshold_percent) }}%
            </span>
          </td>
          <td>
            <span v-if="s.target_price" class="target-price">¥{{ s.target_price.toFixed(2) }}</span>
            <span v-else style="color:var(--muted)">—</span>
          </td>
          <td>
            <span v-if="s.rebuy_enabled && s.rebuy_date" class="rebuy-tag">
              📣 {{ s.rebuy_date }} {{ s.rebuy_time || '09:00:00' }}
            </span>
            <span v-else style="color:var(--muted)">—</span>
          </td>
          <td>
            <label class="toggle-wrap">
              <input
                type="checkbox"
                :checked="!!s.monitor_enabled"
                @change="onToggle(s.code, $event.target.checked)"
              />
              <span class="toggle-slider"></span>
            </label>
          </td>
          <td>
            <div class="action-btns">
              <button class="btn btn-outline btn-sm" @click="$emit('edit', s)">编辑</button>
              <button class="btn btn-danger btn-sm" @click="$emit('delete', s)">删除</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { useStockStore } from '@/stores/stockStore.js'
import { useToast } from '@/composables/useToast.js'

const store = useStockStore()
const { toast } = useToast()

/**
 * @prop {Array} stocks
 */
defineProps({
  stocks: { type: Array, default: () => [] }
})

defineEmits(['add', 'edit', 'delete'])

/**
 * @param {Object} s
 * @returns {'up'|'down'|'flat'}
 */
function priceClass(s) {
  if (s.change_percent == null) return 'flat'
  if (s.change_percent > 0) return 'up'
  if (s.change_percent < 0) return 'down'
  return 'flat'
}

/**
 * @param {string} code
 * @param {boolean} enabled
 */
async function onToggle(code, enabled) {
  await store.toggleMonitor(code, enabled)
  toast(enabled ? '监控已开启' : '监控已暂停', 'ok')
}
</script>
