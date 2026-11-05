<script setup>
import { computed, watch } from 'vue'
import { Filter, X } from '@lucide/vue'

const model = defineModel({ type: Object, required: true })
const props = defineProps({
  datasets: { type: Array, required: true },
  scalar: Boolean,
  temporal: Boolean,
})
const dataset = computed(() => props.datasets.find((d) => d.id === model.value.dataset_id))
const columns = computed(() => dataset.value?.schema || [])
const numbers = computed(() => columns.value.filter((c) => c.kind === 'number'))
const dates = computed(() => columns.value.filter((c) => c.kind === 'date'))

function resetDataset() {
  model.value.field = null
  model.value.date_field = null
  model.value.group_by = []
  model.value.filters = []
  model.value.aggregation = 'count'
}
watch(
  () => model.value.aggregation,
  (value) => {
    if (value === 'count') model.value.field = null
  },
)

function filterValue(event, condition) {
  const column = columns.value.find((c) => c.name === condition.field)
  condition.value =
    column?.kind === 'number'
      ? Number(event.target.value)
      : column?.kind === 'boolean'
        ? event.target.value === 'true'
        : event.target.value
}

function resetFilter(condition) {
  const kind = columns.value.find((c) => c.name === condition.field)?.kind
  condition.value = kind === 'number' ? 0 : kind === 'boolean' ? false : ''
}

function addFilter() {
  const condition = { field: columns.value[0]?.name || '', operator: 'eq', value: '' }
  resetFilter(condition)
  model.value.filters.push(condition)
}
</script>

<template>
  <div class="form-grid">
    <label
      >Dataset<select v-model="model.dataset_id" required @change="resetDataset">
        <option :value="null" disabled>Selecione um dataset</option>
        <option v-for="item in datasets" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select></label
    >
    <label v-if="!temporal && model.group_by.length"
      >Segunda categoria<select
        :value="model.group_by[1] || ''"
        @change="
          model.group_by = $event.target.value
            ? [model.group_by[0], $event.target.value]
            : model.group_by.slice(0, 1)
        "
      >
        <option value="">Sem segunda categoria</option>
        <option
          v-for="column in columns.filter((c) => c.name !== model.group_by[0])"
          :key="column.name"
          :value="column.name"
        >
          {{ column.name }}
        </option>
      </select></label
    >
    <label
      >Calculo<select v-model="model.aggregation">
        <option value="count">Contagem de registros</option>
        <option value="sum">Soma</option>
        <option value="avg">Media</option>
        <option value="min">Minimo</option>
        <option value="max">Maximo</option>
      </select></label
    >
    <label v-if="model.aggregation !== 'count'"
      >Coluna numerica<select v-model="model.field" required>
        <option :value="null" disabled>Selecione uma coluna</option>
        <option v-for="column in numbers" :key="column.name" :value="column.name">
          {{ column.name }}
        </option>
      </select></label
    >
    <template v-if="!scalar">
      <label v-if="!temporal"
        >Agrupar por categoria<select
          :value="model.group_by[0] || ''"
          @change="model.group_by = $event.target.value ? [$event.target.value] : []"
        >
          <option value="">Sem agrupamento</option>
          <option v-for="column in columns" :key="column.name" :value="column.name">
            {{ column.name }}
          </option>
        </select></label
      >
      <label
        >Coluna de data<select v-model="model.date_field" :required="temporal">
          <option :value="null">{{ temporal ? 'Selecione uma data' : 'Sem periodo' }}</option>
          <option v-for="column in dates" :key="column.name" :value="column.name">
            {{ column.name }}
          </option>
        </select></label
      >
      <label v-if="model.date_field"
        >Periodo<select v-model="model.period">
          <option value="day">Dia</option>
          <option value="week">Semana</option>
          <option value="month">Mes</option>
          <option value="year">Ano</option>
        </select></label
      >
    </template>
  </div>
  <template v-if="!temporal">
    <div v-for="(condition, index) in model.filters" :key="index" class="filter-row">
      <label
        >Coluna do filtro<select v-model="condition.field" @change="resetFilter(condition)">
          <option v-for="column in columns" :key="column.name" :value="column.name">
            {{ column.name }}
          </option>
        </select></label
      >
      <label
        >Condicao<select v-model="condition.operator">
          <option value="eq">Igual</option>
          <option value="ne">Diferente</option>
          <option value="gt">Maior</option>
          <option value="gte">Maior ou igual</option>
          <option value="lt">Menor</option>
          <option value="lte">Menor ou igual</option>
          <option value="contains">Contem (texto)</option>
        </select></label
      >
      <label
        >Valor<select
          v-if="columns.find((c) => c.name === condition.field)?.kind === 'boolean'"
          v-model="condition.value"
        >
          <option :value="true">Verdadeiro</option>
          <option :value="false">Falso</option></select
        ><input
          v-else
          :value="condition.value"
          :type="
            columns.find((c) => c.name === condition.field)?.kind === 'number' ? 'number' : 'text'
          "
          step="any"
          required
          placeholder="Valor; datas em ISO"
          @input="filterValue($event, condition)"
      /></label>
      <button type="button" class="button secondary" @click="model.filters.splice(index, 1)">
        <X :size="14" /> Remover filtro
      </button>
    </div>
    <button
      type="button"
      class="button secondary small"
      :disabled="!columns.length || model.filters.length >= 10"
      @click="addFilter"
    >
      <Filter :size="14" /> Adicionar filtro
    </button>
    <p v-if="model.filters.length" class="muted small">
      Todos os filtros são aplicados em conjunto (E). Até 10 condições.
    </p>
  </template>
</template>
