/**
 * composables/useToast.js — Toast 通知 composable
 */
import { ref } from 'vue'

/** @type {import('vue').Ref<Array<{id: number, msg: string, type: string}>>} */
const toasts = ref([])
let nextId = 1

/**
 * @param {string} msg
 * @param {'ok'|'err'|'info'} type
 * @param {number} [duration=3000]
 */
export function useToast() {
  function toast(msg, type = 'ok', duration = 3000) {
    const id = nextId++
    toasts.value.push({ id, msg, type })
    setTimeout(() => {
      const idx = toasts.value.findIndex(t => t.id === id)
      if (idx !== -1) toasts.value.splice(idx, 1)
    }, duration)
  }

  return { toasts, toast }
}
