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
  { title: 'Importe seus dados', to: '/ingestion', done: props.summary.user_imports > 0 },
  { title: 'Execute uma análise', to: '/analytics', done: props.summary.analytics_queries > 0 },
  { title: 'Salve um relatório', to: '/reports', done: props.summary.reports > 0 },
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
          {{ steps.filter((step) => step.done).length }} de {{ steps.length }} etapas concluídas.
        </p>
      </div>
      <button class="icon-button" aria-label="Ocultar guia de primeiros passos" @click="toggle">
        <X :size="16" />
      </button>
    </div>
    <p v-if="!auth.canEdit" class="muted small">
      Seu acesso é de leitura. Peça a um editor ou administrador para cadastrar e importar dados.
    </p>
    <p v-else class="muted small">
      Escolha um dataset, importe seus dados, explore os resultados na central de análises e salve
      uma consulta como relatório.
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
