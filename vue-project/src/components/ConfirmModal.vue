<template>
  <div class="modal-overlay" :class="{ show: show }" @click.self="$emit('cancel')">
    <div class="modal-confirm">
      <div class="confirm-icon">🗑️</div>
      <h2>{{ title }}</h2>
      <p>{{ message }}</p>
      <div class="confirm-actions">
        <button class="btn btn-outline" @click="$emit('cancel')">取消</button>
        <button class="btn btn-danger" @click="$emit('confirm')">{{ confirmText }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * @prop {boolean} show
 * @prop {string} [title='确认删除']
 * @prop {string} [message='']
 * @prop {string} [confirmText='确认删除']
 */
defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '确认删除' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确认删除' },
})

defineEmits(['confirm', 'cancel'])
</script>
