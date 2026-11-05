<script setup>
import { onMounted, ref } from 'vue'
import { Star, Trash2 } from '@lucide/vue'
import { allPages, api, post } from '@/services/api'
import Notification from './ui/Notification.vue'
import AppDialog from './ui/AppDialog.vue'
defineProps({ query: { type: Object, required: true } })
const emit = defineEmits(['select'])
const favorites = ref([])
const name = ref('')
const error = ref('')
const busy = ref(false)
const removing = ref(null)
async function load() {
  favorites.value = await allPages('/favorites')
}
async function save(query) {
  busy.value = true
  error.value = ''
  try {
    await post('/favorites', { name: name.value, query })
    name.value = ''
    await load()
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}
async function remove() {
  busy.value = true
  error.value = ''
  try {
    await api(`/favorites/${removing.value.id}`, { method: 'DELETE' })
    removing.value = null
    await load()
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try {
    await load()
  } catch (exc) {
    error.value = exc.message
  }
})
</script>
<template>
  <section class="panel favorites-panel">
    <h2><Star :size="17" /> Consultas e filtros favoritos</h2>
    <p class="muted small">
      Favoritos pessoais. Salva a consulta e os filtros atuais, incluindo o período quando
      aplicável.
    </p>
    <Notification v-if="error" :message="error" kind="error" @dismiss="error = ''" />
    <form class="favorite-form" @submit.prevent="save(query)">
      <label
        >Nome do favorito<input
          v-model="name"
          required
          minlength="2"
          maxlength="100"
          placeholder="Ex.: Receita mensal por canal"
      /></label>
      <button class="button secondary" :disabled="busy || !query.dataset_id">
        <Star :size="14" /> Salvar favorito
      </button>
    </form>
    <ul class="favorite-list">
      <li v-for="item in favorites" :key="item.id">
        <button
          type="button"
          class="text-button"
          @click="emit('select', JSON.parse(JSON.stringify(item.query)))"
        >
          {{ item.name }}
        </button>
        <button
          type="button"
          class="icon-button"
          :aria-label="`Excluir favorito ${item.name}`"
          :disabled="busy"
          @click="removing = item"
        >
          <Trash2 :size="14" />
        </button>
      </li>
    </ul>
    <p v-if="!favorites.length" class="muted small">Nenhum favorito salvo.</p>
    <AppDialog :open="!!removing" title="Excluir favorito?" @close="removing = null">
      <p>Remover “{{ removing?.name }}” dos seus favoritos?</p>
      <template #footer
        ><button class="button secondary" :disabled="busy" @click="removing = null">Cancelar</button
        ><button class="button" :disabled="busy" @click="remove">Excluir favorito</button></template
      >
    </AppDialog>
  </section>
</template>
