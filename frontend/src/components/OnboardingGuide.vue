<script setup>
import { computed, ref } from 'vue'
import { Check, ArrowRight, X } from '@lucide/vue'
import { useAuthStore } from '@/stores/auth'
const props = defineProps({ summary: { type: Object, required: true } })
const auth = useAuthStore()
const key = `datapulse-onboarding-${auth.user.id}`
const hidden = ref(localStorage.getItem(key) === 'hidden')
function toggle() {
  hidden.value = !hidden.value
  localStorage.setItem(key, hidden.value ? 'hidden' : 'visible')
}
const steps = computed(() => [
  { title: 'Cadastre uma fonte', to: '/sources', done: props.summary.sources > 0 },
  { title: 'Crie seu dataset', to: '/datasets', done: props.summary.datasets > 0 },
  { title: 'Importe dados', to: '/ingestion', done: props.summary.records > 0 },
  { title: 'Defina seu primeiro KPI', to: '/kpis', done: props.summary.kpi_count > 0 },
])
</script>
<template>
  <button v-if="hidden" class="text-button onboarding-reopen" @click="toggle">
    Mostrar guia de primeiros passos
  </button>
  <section v-else class="panel onboarding-panel">
    <div class="panel-heading">
      <div>
        <h2>Primeiros passos no DataPulse</h2>
        <p class="muted small">
          {{ steps.filter((step) => step.done).length }} de 4 etapas concluídas com dados reais.
        </p>
      </div>
      <button class="icon-button" aria-label="Ocultar guia de primeiros passos" @click="toggle">
        <X :size="16" />
      </button>
    </div>
    <p v-if="!auth.canEdit" class="muted small">
      Seu acesso é de leitura. Peça a um editor ou administrador para cadastrar e importar dados.
    </p>
    <ol class="onboarding-steps">
      <li v-for="(step, index) in steps" :key="step.to" :class="{ completed: step.done }">
        <span class="step-number"
          ><Check v-if="step.done" :size="16" /><template v-else>{{ index + 1 }}</template></span
        >
        <RouterLink :to="step.to">{{ step.title }} <ArrowRight :size="14" /></RouterLink>
      </li>
    </ol>
  </section>
</template>
