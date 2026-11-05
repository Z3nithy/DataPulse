<script setup>
import { computed, ref, useId } from 'vue'
import { format } from '@/services/api'
import { useReveal } from '@/composables/motion'
import EmptyState from './ui/EmptyState.vue'

const props = defineProps({
  groups: { type: Array, required: true },
  title: { type: String, default: 'Evolução dos dados' },
  variant: { type: String, default: 'bar' },
})
const root = ref(null)
const gradientId = useId()
const points = computed(() => props.groups.filter((g) => Number.isFinite(g.value)).slice(-24))
const min = computed(() => Math.min(0, ...points.value.map((p) => p.value)))
const max = computed(() => Math.max(0, ...points.value.map((p) => p.value)))
const y = (value) => 220 - ((value - min.value) / (max.value - min.value || 1)) * 175
const width = computed(() => 620 / (points.value.length || 1))
const x = (index) => 65 + index * width.value + width.value / 2
const line = computed(() =>
  points.value
    .map((point, index) => `${index ? 'L' : 'M'} ${x(index)} ${y(point.value)}`)
    .join(' '),
)
const area = computed(() =>
  points.value.length
    ? `${line.value} L ${x(points.value.length - 1)} ${y(0)} L ${x(0)} ${y(0)} Z`
    : '',
)
const label = (point) => Object.values(point.group).join(' / ')
useReveal(root, () => props.groups)
</script>
<template>
  <div ref="root" class="chart">
    <div v-if="points.length" data-reveal>
      <svg viewBox="0 0 720 270" role="img" :aria-label="title">
        <title>{{ title }}</title>
        <defs>
          <linearGradient :id="gradientId" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="#6366f1" stop-opacity=".32" />
            <stop offset="100%" stop-color="#6366f1" stop-opacity="0" />
          </linearGradient>
        </defs>
        <g v-for="tick in [0, 1, 2, 3, 4]" :key="tick">
          <line
            x1="65"
            :y1="45 + tick * 43.75"
            x2="695"
            :y2="45 + tick * 43.75"
            class="chart-grid"
          />
          <text x="54" :y="49 + tick * 43.75" text-anchor="end" class="chart-label">
            {{ format(max - ((max - min) * tick) / 4) }}
          </text>
        </g>
        <line x1="65" :y1="y(0)" x2="695" :y2="y(0)" class="chart-axis" />
        <template v-if="variant === 'area'">
          <path :d="area" :fill="`url(#${gradientId})`" />
          <path
            :d="line"
            fill="none"
            stroke="#818cf8"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </template>
        <g v-for="(point, index) in points" :key="index">
          <circle
            v-if="variant === 'area'"
            :cx="x(index)"
            :cy="y(point.value)"
            r="4"
            fill="#818cf8"
            class="chart-point"
          >
            <title>{{ label(point) }}: {{ format(point.value) }}</title>
          </circle>
          <rect
            v-else
            :x="65 + index * width + 6"
            :y="Math.min(y(point.value), y(0))"
            :width="Math.max(3, width - 12)"
            :height="Math.max(1, Math.abs(y(0) - y(point.value)))"
            rx="4"
            :fill="point.value < 0 ? '#ef4444' : '#6366f1'"
          >
            <title>{{ label(point) }}: {{ format(point.value) }}</title>
          </rect>
          <text
            v-if="points.length <= 8 || index % Math.ceil(points.length / 6) === 0"
            :x="x(index)"
            y="252"
            text-anchor="middle"
            class="chart-label"
          >
            {{ label(point).slice(0, 16) }}
          </text>
        </g>
      </svg>
      <p class="chart-footnote">
        Até 24 grupos observados · passe sobre os pontos para consultar valores.
      </p>
      <details class="chart-accessibility">
        <summary>Consultar valores do gráfico</summary>
        <ul>
          <li v-for="(point, index) in points" :key="index">
            {{ label(point) }}: {{ format(point.value) }}
          </li>
        </ul>
      </details>
    </div>
    <EmptyState
      v-else
      title="Ainda não há uma série para exibir"
      description="Selecione um dataset e uma coluna de data ou categoria. Nenhum valor será simulado."
    />
  </div>
</template>
