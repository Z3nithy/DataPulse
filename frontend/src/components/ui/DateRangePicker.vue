<script setup>
import { computed, ref } from 'vue'
import { CalendarDays, ChevronDown } from '@lucide/vue'
import AppDialog from './AppDialog.vue'
import { useInterfaceStore } from '@/stores/interface'
import { presetRange } from '@/services/dateRange'
const ui = useInterfaceStore()
const open = ref(false)
const draft = ref({ from: '', to: '' })
const label = computed(() =>
  ui.range.from || ui.range.to
    ? `${ui.range.from ? ui.range.from.split('-').reverse().join('/') : 'Início'} — ${ui.range.to ? ui.range.to.split('-').reverse().join('/') : 'Sem limite'}`
    : 'Todo o período',
)
function show() {
  draft.value = { ...ui.range }
  open.value = true
}
function apply() {
  ui.range = { ...draft.value }
  open.value = false
}
</script>
<template>
  <button
    class="button secondary range-trigger"
    type="button"
    aria-haspopup="dialog"
    :aria-expanded="open"
    :aria-label="`Selecionar período: ${label}`"
    @click="show"
  >
    <CalendarDays :size="16" /><span>{{ label }}</span
    ><ChevronDown :size="13" />
  </button>
  <AppDialog :open="open" title="Período das análises" @close="open = false">
    <p class="muted small">
      Aplica-se aos gráficos do dashboard e consultas de Analytics/Tendências com coluna de data. Os
      totais permanecem históricos. Não modifica a criação de KPIs ou relatórios.
    </p>
    <div class="range-presets">
      <button
        v-for="days in [7, 30, 90]"
        :key="days"
        class="button secondary small"
        @click="draft = presetRange(days)"
      >
        Últimos {{ days }} dias</button
      ><button class="button secondary small" @click="draft = presetRange(0)">
        Todo o período
      </button>
    </div>
    <form @submit.prevent="apply">
      <div class="form-grid">
        <label>De<input v-model="draft.from" type="date" :max="draft.to || undefined" /></label
        ><label>Até<input v-model="draft.to" type="date" :min="draft.from || undefined" /></label>
      </div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" @click="open = false">Cancelar</button
        ><button class="button">Aplicar período</button>
      </div>
    </form>
  </AppDialog>
</template>
