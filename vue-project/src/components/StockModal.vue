<template>
  <div class="modal-overlay" :class="{ show: show }" @click.self="handleClose">
    <div class="modal-form">
      <h2>{{ isEdit ? '编辑股票' : '添加股票' }}</h2>

      <!-- 股票代码 -->
      <div class="form-row">
        <label>股票代码 <span class="req">*</span></label>
        <input
          type="text"
          v-model="form.code"
          :disabled="isEdit && !codeChanged"
          :class="{ error: codeError }"
          placeholder="A股如 601857，美股如 AAPL"
          maxlength="10"
          @blur="onCodeBlur"
          @input="onCodeInput"
        />
        <div class="hint" v-if="!codeError && !codeSuccess">
          输入后自动获取名称
        </div>
        <div class="err-msg" v-if="codeError">{{ codeError }}</div>
        <div class="hint" v-if="codeSuccess" style="color:var(--success)">
          ✓ 代码有效
        </div>
      </div>

      <!-- 名称 -->
      <div class="form-row">
        <label>名称</label>
        <input
          type="text"
          v-model="form.name"
          placeholder="自动获取，可手动填写"
        />
      </div>

      <!-- 阈值 -->
      <div class="form-row">
        <label>监控涨跌幅阈值 (%)</label>
        <input
          type="number"
          v-model.number="form.threshold_percent"
          step="0.1"
        />
        <div class="hint">正数监控涨幅，负数监控跌幅（例：5 = 涨5%触发，-5 = 跌5%触发）</div>
      </div>

      <!-- 目标价 -->
      <div class="form-row">
        <label>目标价格（元）</label>
        <input
          type="number"
          v-model.number="form.target_price"
          step="0.01"
          min="0"
          placeholder="留空则不启用"
        />
        <div class="hint" v-if="form.target_price">
          系统将根据目标价与当前价自动判断方向
        </div>
      </div>

      <!-- 目标价方向（可选） -->
      <div class="form-row" v-if="form.target_price">
        <label>目标价方向</label>
        <select v-model.number="form.target_price_direction">
          <option :value="1">止盈（涨到目标价触发）</option>
          <option :value="-1">买入（跌到目标价触发）</option>
        </select>
        <div class="hint">系统已自动判断，可手动修改</div>
      </div>

      <!-- 重新买进提醒日期 -->
      <div class="form-row">
        <label>重新买进提醒日期</label>
        <input type="date" v-model="form.rebuy_date" />
      </div>

      <!-- 重新买进提醒时间 -->
      <div class="form-row">
        <label>提醒时间（精确到秒）</label>
        <input type="time" v-model="form.rebuy_time" step="1" />
        <div class="hint">默认每天 09:00:00</div>
      </div>

      <div class="modal-actions">
        <button class="btn btn-outline" @click="handleClose">取消</button>
        <button class="btn btn-primary" @click="handleSubmit" :disabled="submitting">
          {{ isEdit ? '保存修改' : '添加' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useStockStore } from '@/stores/stockStore.js'
import { useToast } from '@/composables/useToast.js'

/**
 * @prop {boolean} show
 * @prop {Object|null} editStock - 要编辑的股票对象，null 表示添加模式
 */
const props = defineProps({
  show: { type: Boolean, default: false },
  editStock: { type: Object, default: null },
})

const emit = defineEmits(['close', 'saved'])

// Store & toast
const store = useStockStore()
const { toast } = useToast()

// ── 表单状态 ─────────────────────────────────────────────
const defaultForm = () => ({
  code: '',
  name: '',
  threshold_percent: 2.0,
  target_price: null,
  target_price_direction: 1,
  rebuy_date: '',
  rebuy_time: '09:00:00',
  rebuy_enabled: false,
})

/** @type {import('vue').Ref<{code: string, name: string, threshold_percent: number, target_price: number|null, rebuy_date: string, rebuy_time: string, rebuy_enabled: boolean}>} */
const form = ref(defaultForm())

/** @type {import('vue').Ref<string|null>} */
const codeError = ref(null)
/** @type {import('vue').Ref<boolean>} */
const codeSuccess = ref(false)

/** @type {import('vue').Ref<boolean>} */
const submitting = ref(false)

// 原始编辑代码（用于代码变更检测）
/** @type {import('vue').Ref<string|null>} */
const originalCode = ref(null)

// ── 计算属性 ─────────────────────────────────────────────
const isEdit = computed(() => !!props.editStock)

// 检测用户是否修改了代码
const codeChanged = computed(() => {
  if (!props.editStock) return false
  return form.value.code.toLowerCase() !== (props.editStock.code || '').toLowerCase()
})

// ── 监听 show 变化：初始化 / 重置表单 ─────────────────────
watch(() => props.show, (val) => {
  if (val) {
    if (props.editStock) {
      // 编辑模式
      const s = props.editStock
      originalCode.value = s.code
      form.value = {
        code: s.code || '',
        name: s.name || '',
        threshold_percent: s.threshold_percent ?? 2.0,
        target_price: s.target_price ?? null,
        target_price_direction: s.target_price_direction ?? 1,
        rebuy_date: s.rebuy_date || '',
        rebuy_time: s.rebuy_time || '09:00:00',
        rebuy_enabled: !!s.rebuy_enabled,
      }
    } else {
      // 添加模式
      originalCode.value = null
      form.value = defaultForm()
    }
    codeError.value = null
    codeSuccess.value = false
    submitting.value = false
  }
})

// ── 代码输入处理 ─────────────────────────────────────────
function onCodeInput() {
  codeError.value = null
  codeSuccess.value = false
  // 美股代码自动转大写
  form.value.code = form.value.code.toUpperCase()
}

/**
 * @returns {Promise<void>}
 */
async function onCodeBlur() {
  const raw = (form.value.code || '').trim().replace(/^(SH|SZ)/i, '')
  if (!raw) return

  // 前端格式校验
  if (!/^\d{6}$/.test(raw) && !/^[A-Z]{2,5}$/i.test(raw)) {
    codeError.value = '代码格式错误，A股为6位数字（如 601857），美股为2-5字母（如 AAPL）'
    return
  }

  form.value.code = raw.toUpperCase()

  // 重复检测
  const exclude = props.editStock && !codeChanged.value ? props.editStock.code : null
  const result = await store.checkCode(raw.toLowerCase(), exclude)
  if (!result.ok) {
    codeError.value = result.error || '该代码不可用'
    codeSuccess.value = false
    return
  }

  codeError.value = null
  codeSuccess.value = true

  // 自动获取名称
  if (!form.value.name) {
    const nameResult = await store.fetchStockName(raw.toLowerCase())
    if (nameResult.ok && nameResult.name) {
      form.value.name = nameResult.name
    }
  }
}

// ── 提交 ─────────────────────────────────────────────────
async function handleSubmit() {
  const f = form.value
  if (!f.code) {
    toast('股票代码不能为空', 'err')
    return
  }

  const codeRaw = f.code.trim().replace(/^(SH|SZ)/i, '')
  if (!/^\d{6}$/.test(codeRaw) && !/^[A-Z]{2,5}$/i.test(codeRaw)) {
    toast('代码格式错误，A股为6位数字（如 601857），美股为2-5字母（如 AAPL）', 'err')
    return
  }

  submitting.value = true

  const payload = {
    name: f.name,
    threshold_percent: f.threshold_percent,
    target_price: f.target_price || null,
    target_price_direction: f.target_price_direction,
    rebuy_enabled: !!f.rebuy_date,
    rebuy_date: f.rebuy_date || null,
    rebuy_time: f.rebuy_time || '09:00:00',
  }

  // 如果代码有变更或新增模式，附上代码
  if (isEdit.value && codeChanged.value) {
    payload.code = codeRaw.toLowerCase()
  } else if (!isEdit.value) {
    payload.code = codeRaw.toLowerCase()
  }

  let result
  if (isEdit.value) {
    result = await store.updateStock(originalCode.value, payload)
  } else {
    result = await store.addStock(payload)
  }

  submitting.value = false

  if (result.ok) {
    emit('close')
    emit('saved')
    toast(isEdit.value ? '保存成功' : '添加成功', 'ok')
  } else {
    toast(result.error || '操作失败', 'err')
  }
}

function handleClose() {
  emit('close')
}
</script>
