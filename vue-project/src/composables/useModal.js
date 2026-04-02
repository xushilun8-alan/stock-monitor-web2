/**
 * composables/useModal.js — Modal 状态 composable
 */
import { ref } from 'vue'

export function useModal() {
  /** @type {import('vue').Ref<boolean>} */
  const show = ref(false)

  function open() { show.value = true }
  function close() { show.value = false }

  return { show, open, close }
}
