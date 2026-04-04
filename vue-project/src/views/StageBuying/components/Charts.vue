<template>
  <div class="charts-wrap">
    <div class="chart-item">
      <h4>📈 阶段价格趋势</h4>
      <div ref="priceChartRef" class="chart"></div>
    </div>
    <div class="chart-item">
      <h4>📊 收益分析</h4>
      <div ref="returnChartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'

const props = defineProps({
  stages: { type: Array, default: () => [] },
  currentPrice: { type: Number, default: null },
})

const priceChartRef = ref(null)
const returnChartRef = ref(null)

let priceChart = null
let returnChart = null

// 动态导入 echarts
let echarts = null
async function getEcharts() {
  if (!echarts) {
    try {
      echarts = await import('echarts')
    } catch {
      return null
    }
  }
  return echarts
}

onMounted(async () => {
  const ec = await getEcharts()
  if (!ec || !priceChartRef.value || !returnChartRef.value) return

  priceChart = ec.init(priceChartRef.value)
  returnChart = ec.init(returnChartRef.value)

  renderCharts(ec)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  priceChart?.dispose()
  returnChart?.dispose()
  window.removeEventListener('resize', handleResize)
})

watch(() => [props.stages, props.currentPrice], async () => {
  const ec = await getEcharts()
  if (ec) renderCharts(ec)
}, { deep: true })

function handleResize() {
  priceChart?.resize()
  returnChart?.resize()
}

async function renderCharts(ec) {
  if (!props.stages?.length) return

  const xData = props.stages.map(s => `第${s.stage_number}阶段`)
  const buyPrices = props.stages.map(s => s.buy_price)
  const targets = props.stages.map(s => s.target_income)
  const expectedReturns = props.stages.map(s => s.expected_return)
  const floorLosses = props.stages.map(s => s.floor_loss)

  // 价格趋势图
  const priceOption = {
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>买入价: ¥${p[0].value?.toFixed(4) || '—'}` },
    grid: { left: 60, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: xData, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '买入单价(¥)', axisLabel: { fontSize: 10, formatter: v => v.toFixed(2) } },
    series: [
      {
        name: '买入单价',
        type: 'line',
        data: buyPrices,
        smooth: true,
        lineStyle: { color: '#1976d2', width: 2 },
        itemStyle: { color: '#1976d2' },
        markLine: props.currentPrice ? {
          silent: true,
          data: [{ yAxis: props.currentPrice, lineStyle: { color: '#e53935', type: 'dashed' }, label: { formatter: `当前价 ${props.currentPrice.toFixed(2)}`, fontSize: 10 } }]
        } : undefined,
      },
    ],
  }
  priceChart?.setOption(priceOption, true)

  // 收益分析图（柱状图）
  const returnOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['期望收益', '底价亏损'], top: 0, right: 0, textStyle: { fontSize: 10 } },
    grid: { left: 60, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: xData, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '金额(¥)', axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '期望收益',
        type: 'bar',
        data: expectedReturns.map(v => v ?? 0),
        itemStyle: { color: '#43a047' },
      },
      {
        name: '底价亏损',
        type: 'bar',
        data: floorLosses.map(v => v ?? 0),
        itemStyle: { color: '#e53935' },
      },
    ],
  }
  returnChart?.setOption(returnOption, true)
}
</script>

<style scoped>
.charts-wrap {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-top: 1px solid #1f2d45;
}

.chart-item {
  flex: 1;
  min-width: 300px;
}

.chart-item h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #f1f5f9;
}

.chart {
  width: 100%;
  height: 180px;
}
</style>
