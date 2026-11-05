<script setup>
import { computed } from 'vue'
import { format } from '@/services/api'
import EmptyState from './ui/EmptyState.vue'
const props = defineProps({ groups: { type: Array, required: true } })
const colors = ['#6366f1', '#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#64748b']
const segments = computed(() => {
  const sorted = props.groups.filter((g) => g.count > 0).sort((a, b) => b.count - a.count)
  const top = sorted.slice(0, 5).map((g) => ({
    label: Object.values(g.group)
      .map((v) => v ?? 'Não informado')
      .join(' / '),
    value: g.count,
  }))
  if (sorted.length > 5)
    top.push({
      label: 'Outras categorias',
      value: sorted.slice(5).reduce((sum, g) => sum + g.count, 0),
    })
  return top
})
const total = computed(() => segments.value.reduce((sum, item) => sum + item.value, 0))
const gradient = computed(() => {
  let start = 0
  return `conic-gradient(${segments.value
    .map((item, index) => {
      const end = start + (item.value / total.value) * 100
      const value = `${colors[index]} ${start}% ${end}%`
      start = end
      return value
    })
    .join(',')})`
})
</script>
<template>
  <div v-if="total" class="distribution">
    <div
      class="donut"
      :style="{ background: gradient }"
      role="img"
      :aria-label="`Distribuição de ${total} registros por categoria`"
    >
      <div>
        <strong>{{ format(total) }}</strong
        ><span>registros</span>
      </div>
    </div>
    <ul class="distribution-legend">
      <li v-for="(item, index) in segments" :key="item.label">
        <span class="legend-dot" :style="{ background: colors[index] }" /><span>{{
          item.label
        }}</span
        ><strong>{{ format((item.value / total) * 100) }}%</strong
        ><span class="sr-only">{{ item.value }} registros</span>
      </li>
    </ul>
  </div>
  <EmptyState
    v-else
    title="Encontre padrões por categoria"
    description="Uma coluna de texto permite comparar a distribuição dos registros."
  />
</template>
