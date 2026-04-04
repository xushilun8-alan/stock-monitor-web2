<template>
  <div class="nav-tabs">
    <button
      class="nav-tab"
      :class="{ active: activeTab === 'monitor' }"
      @click="$emit('change', 'monitor')"
    >
      监控列表
    </button>
    <button
      class="nav-tab"
      :class="{ active: activeTab === 'stage-buying' }"
      @click="$emit('change', 'stage-buying')"
    >
      阶段买入
    </button>
    <button
      class="nav-tab"
      :class="{ active: activeTab === 'deleted' }"
      @click="$emit('change', 'deleted')"
    >
      回收站
      <span v-if="deletedCount > 0" class="nav-badge">{{ deletedCount }}</span>
    </button>
  </div>
</template>

<script setup>
/**
 * @prop {string} activeTab - 'monitor' | 'stage-buying' | 'deleted'
 * @prop {number} deletedCount
 */
defineProps({
  activeTab: { type: String, default: 'monitor' },
  deletedCount: { type: Number, default: 0 },
})

/** @type {(tab: string) => void} */
defineEmits(['change'])
</script>
