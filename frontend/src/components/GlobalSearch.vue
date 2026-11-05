<script setup>
import { computed, ref, watch } from 'vue'
import { Search, ArrowUpRight, Database, PlugZap, Gauge } from '@lucide/vue'
import AppDialog from './ui/AppDialog.vue'
import LoadingState from './ui/LoadingState.vue'
import Notification from './ui/Notification.vue'
import { navigation } from '@/services/navigation'
import { allPages } from '@/services/api'
const props = defineProps({ open: Boolean })
defineEmits(['close'])
const search = ref('')
const resources = ref([])
const busy = ref(false)
const error = ref('')
let generation = 0
const items = computed(() =>
  [
    ...navigation.map((item) => ({
      ...item,
      id: item.path,
      category: 'Página',
      to: `/${item.path}`,
    })),
    ...resources.value,
  ]
    .filter((item) =>
      `${item.label} ${item.category}`
        .toLocaleLowerCase('pt-BR')
        .includes(search.value.toLocaleLowerCase('pt-BR')),
    )
    .slice(0, 20),
)
watch(
  () => props.open,
  async (open) => {
    const current = ++generation
    if (!open) return
    search.value = ''
    busy.value = true
    error.value = ''
    resources.value = []
    try {
      const [datasets, sources, kpis] = await Promise.all([
        allPages('/datasets'),
        allPages('/sources'),
        allPages('/kpis'),
      ])
      if (generation !== current) return
      resources.value = [
        ...datasets.map((item) => ({
          id: item.id,
          label: item.name,
          category: 'Dataset',
          to: `/datasets?search=${encodeURIComponent(item.name)}`,
          icon: Database,
        })),
        ...sources.map((item) => ({
          id: item.id,
          label: item.name,
          category: 'Fonte',
          to: `/sources?search=${encodeURIComponent(item.name)}`,
          icon: PlugZap,
        })),
        ...kpis.map((item) => ({
          id: item.id,
          label: item.name,
          category: 'KPI',
          to: `/kpis?search=${encodeURIComponent(item.name)}`,
          icon: Gauge,
        })),
      ]
    } catch (exc) {
      if (current === generation) error.value = exc.message
    } finally {
      if (current === generation) busy.value = false
    }
  },
)
</script>
<template>
  <AppDialog :open="open" title="Busca global" @close="$emit('close')">
    <label class="search-input"
      ><Search :size="18" /><input
        v-model="search"
        type="search"
        placeholder="Buscar páginas, datasets, fontes e KPIs..."
        aria-label="Buscar no workspace"
        autofocus
        autocomplete="off"
      /><kbd>ESC</kbd></label
    >
    <LoadingState v-if="busy" /><Notification
      v-if="error"
      :message="error"
      kind="error"
      @dismiss="error = ''"
    />
    <p class="eyebrow search-count">
      {{ items.length }} RESULTADOS{{ busy ? ' · CARREGANDO RECURSOS' : '' }}
    </p>
    <div class="search-results">
      <RouterLink
        v-for="item in items"
        :key="`${item.category}:${item.id}`"
        :to="item.to"
        @click="$emit('close')"
        ><component :is="item.icon" :size="18" /><span
          ><strong>{{ item.label }}</strong
          ><small>{{ item.category }}</small></span
        ><ArrowUpRight :size="15"
      /></RouterLink>
      <p v-if="!items.length" class="empty">Nenhum resultado para “{{ search }}”.</p>
    </div>
    <p class="muted small">
      Busque pelo nome. A seleção de um recurso abre sua lista com filtro de busca.
    </p>
  </AppDialog>
</template>
