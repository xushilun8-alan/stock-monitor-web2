<template>
  <div class="toast-container">
    <TransitionGroup name="fade">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="t.type"
      >
        {{ t.msg }}
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useToast } from '@/composables/useToast.js'
const { toasts } = useToast()
</script>
