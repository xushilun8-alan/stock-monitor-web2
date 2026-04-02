<template>
  <div class="table-card">
    <div class="deleted-banner" style="margin:16px 16px -8px">
      <span>ℹ️</span>
      <span>已删除股票保留在数据库中，可随时恢复。彻底删除后将永久移除。</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>股票代码</th>
          <th>股票名称</th>
          <th>现价</th>
          <th>涨跌幅阈值</th>
          <th>目标价</th>
          <th>重新买进提醒</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="stocks.length === 0">
          <td colspan="7">
            <div class="empty-state">
              <p>暂无已删除股票</p>
            </div>
          </td>
        </tr>
        <tr v-for="s in stocks" :key="s.code" class="deleted-row">
          <td><strong style="font-size:0.9rem">{{ s.code.toUpperCase() }}</strong></td>
          <td>
            <span v-if="s.name || s.price_name" style="color:var(--muted)">
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
            <div class="action-btns">
              <button class="btn btn-success btn-sm" @click="$emit('restore', s)">恢复</button>
              <button class="btn btn-danger btn-sm" @click="$emit('destroy', s)">彻底删除</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
/**
 * @prop {Array} stocks
 */
defineProps({
  stocks: { type: Array, default: () => [] }
})

/** @type {(s: Object) => 'up'|'down'|'flat'} */
function priceClass(s) {
  if (s.change_percent == null) return 'flat'
  if (s.change_percent > 0) return 'up'
  if (s.change_percent < 0) return 'down'
  return 'flat'
}

defineEmits(['restore', 'destroy'])
</script>
