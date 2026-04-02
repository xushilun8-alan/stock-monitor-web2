<template>
  <div class="modal-overlay" :class="{ show: show }" @click.self="$emit('cancel')">
    <div class="modal-confirm">
      <div class="confirm-icon">⚠️</div>
      <h2>彻底删除</h2>
      <p>{{ message }}</p>
      <div class="confirm-actions">
        <button class="btn btn-outline" @click="$emit('cancel')">取消</button>
        <button class="btn btn-danger" @click="$emit('confirm')">彻底删除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * @prop {boolean} show
 * @prop {string} [message='']
 */
defineProps({
  show: { type: Boolean, default: false },
  message: { type: String, default: '此操作不可恢复，确定要永久删除吗？' },
})

defineEmits(['confirm', 'cancel'])
</script>
