<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ stock ? '编辑股票' : '添加股票' }}</h3>
          <button class="close-btn" @click="$emit('close')">×</button>
        </div>

        <form class="modal-body" @submit.prevent="handleSubmit">
          <div class="form-row">
            <div class="form-group">
              <label>股票代码 *</label>
              <input v-model="form.code" type="text" placeholder="如 601857 或 AAPL" :disabled="!!stock" />
            </div>
            <div class="form-group">
              <label>股票名称</label>
              <input v-model="form.name" type="text" placeholder="自动获取，可手动填写" />
            </div>
          </div>

          <div class="form-section-title">价格参数</div>
          <div class="form-row">
            <div class="form-group">
              <label>初始单价 *</label>
              <input v-model.number="form.initial_price" type="number" step="0.001" min="0" required />
            </div>
            <div class="form-group">
              <label>目标价基准</label>
              <input v-model.number="form.target_price" type="number" step="0.001" min="0" placeholder="不设置则不计算目标收益" />
            </div>
            <div class="form-group">
              <label>底价</label>
              <input v-model.number="form.floor_price" type="number" step="0.001" min="0" placeholder="不设置则不计算亏损" />
            </div>
          </div>

          <div class="form-section-title">股数参数</div>
          <div class="form-row">
            <div class="form-group">
              <label>初始股数（阶段1）*</label>
              <input v-model.number="form.initial_shares" type="number" min="1" required />
            </div>
            <div class="form-group">
              <label>每阶股数 *</label>
              <input v-model.number="form.per_stage_shares" type="number" min="1" required />
            </div>
            <div class="form-group">
              <label>总阶段数 *</label>
              <input v-model.number="form.stage_count" type="number" min="2" max="20" required />
            </div>
          </div>

          <div class="form-section-title">算法参数</div>
          <div class="form-row">
            <div class="form-group">
              <label>序号系数</label>
              <input v-model.number="form.serial_coefficient" type="number" step="0.001" min="0" />
            </div>
            <div class="form-group">
              <label>幅度系数</label>
              <input v-model.number="form.amplitude_coefficient" type="number" step="0.001" min="0" />
            </div>
            <div class="form-group">
              <label>跌幅系数</label>
              <input v-model.number="form.decline_coefficient" type="number" step="0.001" min="0" max="1" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>最小幅度</label>
              <input v-model.number="form.min_amplitude" type="number" step="0.001" min="0" max="1" />
            </div>
            <div class="form-group">
              <label>幅度乘数</label>
              <input v-model.number="form.amplitude_multiplier" type="number" step="0.0001" min="0" />
            </div>
          </div>

          <div v-if="submitError" class="form-error">{{ submitError }}</div>

          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="$emit('close')">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              {{ submitting ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useStageBuyingStore } from '../store.js'

const props = defineProps({
  show: Boolean,
  stock: Object,
})
const emit = defineEmits(['close', 'saved'])

const store = useStageBuyingStore()

const defaultForm = () => ({
  code: '',
  name: '',
  initial_price: null,
  initial_shares: null,
  per_stage_shares: null,
  stage_count: 9,
  serial_coefficient: 1.0,
  amplitude_coefficient: 0.08,
  decline_coefficient: 0.975,
  target_price: null,
  min_amplitude: 0.98,
  amplitude_multiplier: 1.001,
  floor_price: null,
})

const form = ref(defaultForm())
const submitting = ref(false)
const submitError = ref('')

watch(() => props.show, (val) => {
  if (val) {
    submitError.value = ''
    if (props.stock) {
      form.value = {
        code: props.stock.code,
        name: props.stock.name || '',
        initial_price: props.stock.initial_price,
        initial_shares: props.stock.initial_shares,
        per_stage_shares: props.stock.per_stage_shares,
        stage_count: props.stock.stage_count,
        serial_coefficient: props.stock.serial_coefficient,
        amplitude_coefficient: props.stock.amplitude_coefficient,
        decline_coefficient: props.stock.decline_coefficient,
        target_price: props.stock.target_price,
        min_amplitude: props.stock.min_amplitude,
        amplitude_multiplier: props.stock.amplitude_multiplier,
        floor_price: props.stock.floor_price,
      }
    } else {
      form.value = defaultForm()
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  submitError.value = ''
  try {
    const data = { ...form.value }
    // 清理空值
    if (data.target_price === '' || data.target_price === null) data.target_price = null
    if (data.floor_price === '' || data.floor_price === null) data.floor_price = null

    let res
    if (props.stock) {
      res = await store.updateStock(props.stock.id, data)
    } else {
      res = await store.addStock(data)
    }
    if (res.ok) {
      emit('saved')
    } else {
      submitError.value = res.error || '操作失败'
    }
  } catch (e) {
    submitError.value = e.message
  } finally {
    submitting.value = false
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
  max-width: 640px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #1f2d45;
}

.modal-header h3 { margin: 0; font-size: 16px; color: #f1f5f9; }

.close-btn {
  background: none;
  border: none;
  font-size: 22px;
  cursor: pointer;
  color: #64748b;
}

.modal-body { padding: 16px 20px; }

.form-section-title {
  font-size: 12px;
  color: #64748b;
  margin: 12px 0 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #1f2d45;
}

.form-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.form-group {
  flex: 1;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.form-group label {
  font-size: 12px;
  color: #94a3b8;
}

.form-group input {
  padding: 6px 8px;
  border: 1px solid #1f2d45;
  border-radius: 4px;
  font-size: 13px;
  background: #0a0f1e;
  color: #f1f5f9;
}

.form-group input:disabled {
  background: #1a2332;
}

.form-error {
  color: #e53935;
  font-size: 12px;
  margin-bottom: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #1f2d45;
  margin-top: 4px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 4px;
  border: 1px solid #1f2d45;
  background: #111827;
  color: #f1f5f9;
  cursor: pointer;
  font-size: 13px;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #38bdf8; color: #0a0f1e; border-color: #38bdf8; }
.btn-primary:hover:not(:disabled) { background: #7dd3fc; }
.btn-outline { background: transparent; }
.btn-outline:hover { background: rgba(255,255,255,0.05); }
</style>
