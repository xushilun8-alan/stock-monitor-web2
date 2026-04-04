<template>
  <div class="stage-table-wrap">
    <table class="stage-table">
      <thead>
        <tr>
          <th>阶段</th>
          <th>幅度</th>
          <th>买入单价</th>
          <th>股数</th>
          <th>买入金额</th>
          <th>底价亏损</th>
          <th>亏损率%</th>
          <th>目标收益</th>
          <th>期望收益</th>
          <th>收益率%</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <!-- 全部汇总行 -->
        <tr class="summary-row all-summary">
          <td colspan="4" class="summary-label">全部阶段汇总</td>
          <td>{{ formatMoney(totalAmount) }}</td>
          <td>{{ formatNum(totalFloorLoss) }}</td>
          <td>{{ formatPct(totalLossRate) }}</td>
          <td>{{ formatMoney(totalTargetIncome) }}</td>
          <td>{{ formatMoney(totalExpectedReturn) }}</td>
          <td>{{ formatPct(totalReturnRate) }}</td>
          <td colspan="2"></td>
        </tr>
        <!-- 已执行汇总行 -->
        <tr class="summary-row exec-summary" v-if="executedStages.length > 0">
          <td colspan="4" class="summary-label">已执行阶段汇总</td>
          <td>{{ formatMoney(execAmount) }}</td>
          <td>{{ formatNum(execFloorLoss) }}</td>
          <td>{{ formatPct(execLossRate) }}</td>
          <td>{{ formatMoney(execTargetIncome) }}</td>
          <td>{{ formatMoney(execExpectedReturn) }}</td>
          <td>{{ formatPct(execReturnRate) }}</td>
          <td colspan="2"></td>
        </tr>

        <!-- 阶段数据行 -->
        <tr
          v-for="stage in stages"
          :key="stage.id"
          :class="{
            'current-stage': isCurrentStage(stage),
            'executed-row': stage.status === 'executed',
            'triggered-row': stage.status === 'triggered',
          }"
        >
          <td class="stage-num">第{{ stage.stage_number }}阶段</td>
          <td>{{ stage.amplitude != null ? stage.amplitude.toFixed(8) : '—' }}</td>
          <td>{{ stage.buy_price != null ? stage.buy_price.toFixed(4) : '—' }}</td>
          <td>{{ stage.shares != null ? stage.shares.toLocaleString() : '—' }}</td>
          <td>{{ formatMoney(stage.buy_amount) }}</td>
          <td :class="stage.floor_loss != null && stage.floor_loss > 0 ? 'loss-val' : ''">
            {{ stage.floor_loss != null ? formatNum(stage.floor_loss) : '—' }}
          </td>
          <td :class="stage.loss_rate != null && stage.loss_rate > 0 ? 'loss-val' : ''">
            {{ stage.loss_rate != null ? formatPct(stage.loss_rate) : '—' }}
          </td>
          <td>{{ stage.target_income != null ? formatMoney(stage.target_income) : '—' }}</td>
          <td :class="stage.expected_return != null && stage.expected_return > 0 ? 'profit-val' : ''">
            {{ stage.expected_return != null ? formatMoney(stage.expected_return) : '—' }}
          </td>
          <td :class="stage.return_rate != null && stage.return_rate > 0 ? 'profit-val' : ''">
            {{ stage.return_rate != null ? formatPct(stage.return_rate) : '—' }}
          </td>
          <td>
            <span class="status-badge" :class="stage.status">
              {{ statusText(stage.status) }}
            </span>
          </td>
          <td>
            <button
              v-if="stage.status === 'triggered'"
              class="btn-exec"
              @click="$emit('toggle', stage.id)"
            >
              标记已执行
            </button>
            <button
              v-else-if="stage.status === 'executed'"
              class="btn-cancel"
              @click="$emit('toggle', stage.id)"
            >
              取消执行
            </button>
            <span v-else class="no-action">—</span>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 图表 -->
    <Charts :stages="stages" :current-price="currentPrice" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Charts from './Charts.vue'

const props = defineProps({
  stages: { type: Array, default: () => [] },
  currentPrice: { type: Number, default: null },
})
defineEmits(['toggle'])

// 当前价格所在阶段
function isCurrentStage(stage) {
  if (props.currentPrice == null) return false
  if (stage.status === 'executed') return false
  // 找到下一个未执行阶段
  const nextUntriggered = props.stages.find(s => s.status === 'untriggered' || s.status === 'triggered')
  return nextUntriggered && nextUntriggered.stage_number === stage.stage_number
}

const statusText = (s) => ({ untriggered: '未触发', triggered: '已触发', executed: '已执行' }[s] || s)

// 汇总计算
const totalAmount = computed(() => props.stages.reduce((s, x) => s + (x.buy_amount || 0), 0))
const totalFloorLoss = computed(() => props.stages.reduce((s, x) => s + (x.floor_loss || 0), 0))
const totalTargetIncome = computed(() => props.stages.reduce((s, x) => s + (x.target_income || 0), 0))
const totalExpectedReturn = computed(() => props.stages.reduce((s, x) => s + (x.expected_return || 0), 0))
const totalLossRate = computed(() => totalAmount.value > 0 ? totalFloorLoss.value / totalAmount.value * 100 : null)
const totalReturnRate = computed(() => totalAmount.value > 0 ? totalExpectedReturn.value / totalAmount.value * 100 : null)

const executedStages = computed(() => props.stages.filter(s => s.status === 'executed'))
const execAmount = computed(() => executedStages.value.reduce((s, x) => s + (x.buy_amount || 0), 0))
const execFloorLoss = computed(() => executedStages.value.reduce((s, x) => s + (x.floor_loss || 0), 0))
const execTargetIncome = computed(() => executedStages.value.reduce((s, x) => s + (x.target_income || 0), 0))
const execExpectedReturn = computed(() => executedStages.value.reduce((s, x) => s + (x.expected_return || 0), 0))
const execLossRate = computed(() => execAmount.value > 0 ? execFloorLoss.value / execAmount.value * 100 : null)
const execReturnRate = computed(() => execAmount.value > 0 ? execExpectedReturn.value / execAmount.value * 100 : null)

function formatMoney(v) {
  if (v == null) return '—'
  return '¥' + v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function formatNum(v) {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(2)
}
function formatPct(v) {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}
</script>

<style scoped>
.stage-table-wrap {
  padding: 12px 16px;
  overflow-x: auto;
}

.stage-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  min-width: 900px;
}

.stage-table th {
  background: #1a2332;
  padding: 6px 8px;
  text-align: right;
  font-weight: 600;
  white-space: nowrap;
  color: #94a3b8;
}

.stage-table td {
  padding: 5px 8px;
  text-align: right;
  border-top: 1px solid #1f2d45;
  color: #f1f5f9;
}

.stage-num { text-align: center !important; font-weight: 500; }

.summary-row td {
  background: #1a2332;
  font-weight: 600;
  border-top: 2px solid #38bdf8;
}

.summary-label { text-align: left !important; }

.executed-row td { background: rgba(34, 197, 94, 0.12); }
.triggered-row td { background: rgba(245, 158, 11, 0.12); }

.current-stage td {
  background: rgba(56, 189, 248, 0.12) !important;
  box-shadow: inset 0 -2px 0 #38bdf8;
}

.status-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
}
.status-badge.untriggered { background: rgba(100, 116, 139, 0.2); color: #94a3b8; }
.status-badge.triggered {
  background: rgba(244, 63, 94, 0.2);
  color: #f43f5e;
  animation: blink 1s infinite;
}
.status-badge.executed { background: rgba(34, 197, 94, 0.2); color: #22c55e; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.profit-val { color: #43a047; }
.loss-val { color: #e53935; }

.btn-exec, .btn-cancel {
  padding: 2px 8px;
  border-radius: 3px;
  border: 1px solid;
  cursor: pointer;
  font-size: 11px;
  background: transparent;
}
.btn-exec { border-color: #22c55e; color: #22c55e; }
.btn-exec:hover { background: rgba(34, 197, 94, 0.15); }
.btn-cancel { border-color: #f59e0b; color: #f59e0b; }
.btn-cancel:hover { background: rgba(245, 158, 11, 0.15); }
.no-action { color: #64748b; }
</style>
