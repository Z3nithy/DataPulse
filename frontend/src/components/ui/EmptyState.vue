<script setup>
import { DatabaseZap } from '@lucide/vue'
defineProps({
  title: { type: String, default: 'Seu próximo insight começa aqui' },
  description: {
    type: String,
    default: 'Adicione uma fonte e importe seus dados para começar a explorar.',
  },
})
</script>
<template>
  <div class="empty">
    <span class="empty-symbol"><DatabaseZap :size="24" aria-hidden="true" /></span>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <slot />
  </div>
</template>
