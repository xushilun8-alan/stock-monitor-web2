<template>
  <div class="settings-bar">
    <label>监控频率</label>
    <input
      type="number"
      v-model.number="localInterval"
      min="10"
      max="3600"
      @keyup.enter="handleSave"
    />
    <span class="unit">秒</span>
    <button class="btn btn-primary btn-sm" @click="handleSave">保存</button>
    <span class="interval-msg" :style="{ display: saved ? 'inline' : 'none' }">
      ✓ 已保存
    </span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useStockStore } from '@/stores/stockStore.js'
import { useToast } from '@/composables/useToast.js'

const props = defineProps({
  interval: { type: Number, default: 60 }
})

const store = useStockStore()
const { toast } = useToast()

/** @type {import('vue').Ref<number>} */
const localInterval = ref(props.interval)
/** @type {import('vue').Ref<boolean>} */
const saved = ref(false)

/** @param {number} val @param {boolean} result */
function showSaved(result) {
  saved.value = result
  if (result) {
    setTimeout(() => { saved.value = false }, 2000)
  }
}

async function handleSave() {
  const secs = localInterval.value
  if (secs < 10) {
    toast('间隔不能小于10秒', 'err')
    return
  }
  const result = await store.saveInterval(secs)
  if (result.ok) {
    showSaved(true)
    toast('监控频率已更新', 'ok')
  } else {
    toast(result.error || '保存失败', 'err')
  }
}
</script>
