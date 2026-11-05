<script setup>
import { computed, ref } from 'vue'
import { format } from '@/services/api'
import { ArrowDownUp, FileCheck2, MoreHorizontal } from '@lucide/vue'
import EmptyState from './ui/EmptyState.vue'

const props = defineProps({
  rows: { type: Array, required: true },
  columns: { type: Array, required: true },
  caption: { type: String, default: 'Dados' },
})
const sortKey = ref('')
const ascending = ref(true)
const sortedRows = computed(() => {
  if (!sortKey.value) return props.rows
  const column = props.columns.find((item) => item.key === sortKey.value)
  return [...props.rows].sort((a, b) => {
    const av = column.render ? column.render(a) : a[sortKey.value]
    const bv = column.render ? column.render(b) : b[sortKey.value]
    if (av == null) return bv == null ? 0 : 1
    if (bv == null) return -1
    const difference =
      typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : format(av).localeCompare(format(bv), 'pt-BR', { numeric: true })
    return ascending.value ? difference : -difference
  })
})
function sort(column) {
  ascending.value = sortKey.value === column.key ? !ascending.value : true
  sortKey.value = column.key
}
</script>

<template>
  <div
    v-if="rows.length"
    class="table-wrap"
    tabindex="0"
    :aria-label="`${caption}: tabela com rolagem horizontal`"
  >
    <table>
      <caption class="sr-only">
        {{
          caption
        }}
      </caption>
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            scope="col"
            :aria-sort="sortKey === column.key ? (ascending ? 'ascending' : 'descending') : 'none'"
          >
            <button
              type="button"
              class="table-sort"
              :aria-label="`Ordenar ${column.label} nesta página`"
              @click="sort(column)"
            >
              <span>{{ column.label }}</span
              ><ArrowDownUp :size="11" aria-hidden="true" />
            </button>
          </th>
          <th v-if="$slots.actions" scope="col">
            <span>Ações</span><MoreHorizontal :size="14" aria-hidden="true" />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in sortedRows" :key="row.id ?? index">
          <td v-for="column in columns" :key="column.key">
            <slot :name="column.key" :row="row">
              <span
                v-if="column.key === 'status'"
                class="badge"
                :class="{
                  success: row.status === 'completed',
                  warning: row.status === 'completed_with_errors',
                  danger: row.status === 'failed',
                }"
                ><FileCheck2 :size="12" />{{
                  {
                    completed: 'Concluído',
                    completed_with_errors: 'Com rejeições',
                    processing: 'Processando',
                    failed: 'Falhou',
                    queued: 'Na fila',
                    running: 'Em execução',
                    sent: 'Enviado',
                    sending: 'Enviando',
                    cancelled: 'Cancelado',
                  }[row.status] || row.status
                }}</span
              >
              <span v-else>{{ column.render ? column.render(row) : format(row[column.key]) }}</span>
            </slot>
          </td>
          <td v-if="$slots.actions"><slot name="actions" :row="row" /></td>
        </tr>
      </tbody>
    </table>
  </div>
  <EmptyState
    v-else
    title="Nenhum registro por aqui"
    description="Os dados aparecerão assim que forem cadastrados ou importados. Se estiver buscando, tente outro termo."
  />
</template>
