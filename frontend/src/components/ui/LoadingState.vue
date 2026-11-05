<script setup>
import { LoaderCircle } from '@lucide/vue'
defineProps({ skeleton: Boolean })
</script>
<template>
  <div role="status" aria-live="polite" :class="skeleton ? 'loading-skeleton' : 'loading'">
    <span class="loading-label"
      ><LoaderCircle :size="16" class="spin" aria-hidden="true" /> Carregando dados...</span
    >
    <div v-if="skeleton" class="skeleton-grid" aria-hidden="true">
      <div v-for="i in 6" :key="i" class="skeleton-card">
        <span class="skeleton" /><strong class="skeleton" /><span class="skeleton short" />
      </div>
    </div>
  </div>
</template>
