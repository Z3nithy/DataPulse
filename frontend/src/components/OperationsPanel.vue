<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { CalendarClock, RefreshCw } from '@lucide/vue'
import { api, post } from '@/services/api'
import DataTable from './DataTable.vue'
import QueryBuilder from './QueryBuilder.vue'
import AppDialog from './ui/AppDialog.vue'
import Notification from './ui/Notification.vue'
const props = defineProps({
  datasets: { type: Array, required: true },
  sources: { type: Array, required: true },
  initialKind: { type: String, default: 'import' },
})
const kind = ref(props.initialKind)
const apiDatasets = computed(() =>
  props.datasets.filter((dataset) =>
    props.sources.some((source) => source.id === dataset.source_id && source.kind === 'api'),
  ),
)
const name = ref('')
const datasetId = ref(null)
const interval = ref(1440)
const emailReport = ref(false)
const query = ref({
  dataset_id: null,
  aggregation: 'count',
  field: null,
  group_by: [],
  date_field: null,
  period: 'month',
  filters: [],
})
const status = ref(null)
const metrics = ref(null)
const schedules = ref([])
const tasks = ref([])
const emails = ref([])
const busy = ref(false)
const error = ref('')
const notice = ref('')
const confirm = ref(null)
let timer
let disposed = false
async function load() {
  busy.value = true
  error.value = ''
  try {
    const [health, scheduleData, taskData, emailData, metricsData] = await Promise.all([
      api('/operations/status'),
      api('/schedules?page_size=100'),
      api('/operations/tasks?page_size=10'),
      api('/operations/emails?page_size=10'),
      api('/operations/metrics'),
    ])
    if (disposed) return
    status.value = health.data
    schedules.value = scheduleData.data
    tasks.value = taskData.data
    emails.value = emailData.data
    metrics.value = metricsData.data
  } catch (exc) {
    if (!disposed) error.value = exc.message
  } finally {
    if (!disposed) busy.value = false
  }
}
async function create() {
  busy.value = true
  notice.value = ''
  error.value = ''
  try {
    await post('/schedules', {
      name: name.value,
      kind: kind.value,
      dataset_id: kind.value === 'report' ? query.value.dataset_id : datasetId.value,
      query: kind.value === 'report' ? query.value : null,
      interval_minutes: interval.value,
      email_report: kind.value === 'report' && emailReport.value,
      enabled: true,
    })
    name.value = ''
    notice.value = 'Agendamento criado. A primeira execução ocorre após o intervalo configurado.'
    await load()
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}
async function toggle() {
  busy.value = true
  error.value = ''
  try {
    const item = confirm.value
    await api(`/schedules/${item.id}`, { method: 'PATCH', body: { enabled: !item.enabled } })
    confirm.value = null
    await load()
  } catch (exc) {
    error.value = exc.message
  } finally {
    busy.value = false
  }
}
async function poll() {
  if (!document.hidden && !busy.value) await load()
  if (!disposed) timer = setTimeout(poll, 15000)
}
onMounted(poll)
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(timer)
})
const date = (value) => (value ? new Date(value).toLocaleString('pt-BR') : 'Ainda não executado')
</script>
<template>
  <section class="panel operations-panel">
    <div class="panel-heading">
      <h2><CalendarClock :size="18" /> Automação e agendamentos</h2>
      <button class="button secondary small" :disabled="busy" @click="load">
        <RefreshCw :size="14" /> Atualizar automações
      </button>
    </div>
    <div v-if="status" class="operation-status">
      <span class="badge" :class="status.worker_online ? 'success' : 'warning'"
        >Worker {{ status.worker_online ? 'online' : 'offline' }}</span
      ><span class="badge">SMTP {{ status.smtp_enabled ? 'habilitado' : 'desabilitado' }}</span>
    </div>
    <p v-if="metrics" class="muted small">
      Fila: {{ metrics.tasks.queued || 0 }} tarefas · {{ metrics.tasks.failed || 0 }} falhas ·
      {{ metrics.emails.queued || 0 }} emails pendentes · {{ metrics.emails.failed || 0 }} emails
      com falha.
    </p>
    <p v-if="status && !status.worker_online" class="message warning">
      O worker não está respondendo. As tarefas ficam na fila até executar
      <code>python -m worker</code> no servidor.
    </p>
    <Notification v-if="error" :message="error" kind="error" @dismiss="error = ''" />
    <Notification v-if="notice" :message="notice" kind="success" @dismiss="notice = ''" />
    <form @submit.prevent="create">
      <div class="form-grid">
        <label
          >Nome do agendamento<input v-model="name" required minlength="2" maxlength="100"
        /></label>
        <label
          >Tipo de automação<select v-model="kind">
            <option value="import">Importar fonte API HTTPS</option>
            <option value="report">Gerar relatório</option>
          </select></label
        >
        <label
          >Intervalo (minutos)<input
            v-model.number="interval"
            type="number"
            min="15"
            max="43200"
            required
        /></label>
        <label v-if="kind === 'import'"
          >Dataset com fonte API<select v-model="datasetId" required>
            <option :value="null" disabled>Selecione</option>
            <option v-for="item in apiDatasets" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        >
      </div>
      <p v-if="kind === 'import' && !apiDatasets.length" class="muted small">
        Cadastre uma fonte API HTTPS e vincule um dataset para agendar importações.
      </p>
      <QueryBuilder v-if="kind === 'report'" v-model="query" :datasets="datasets" />
      <label v-if="kind === 'report'" class="checkbox"
        ><input v-model="emailReport" type="checkbox" :disabled="!status?.smtp_enabled" /> Enviar
        CSV para meu email após gerar</label
      >
      <p class="muted small">
        Horários exibidos no seu fuso; execução armazenada em UTC. Mínimo 15 minutos. Importações
        usam apenas fontes HTTPS autorizadas. Execuções perdidas não são acumuladas. Pausar não
        cancela tarefas já enfileiradas.
      </p>
      <button class="button" :disabled="busy">Criar agendamento</button>
    </form>
    <h3>Agendamentos mais recentes (até 100)</h3>
    <DataTable
      :rows="schedules"
      :columns="[
        { key: 'name', label: 'Nome' },
        { key: 'kind', label: 'Tipo' },
        { key: 'next_run_at', label: 'Próxima execução', render: (r) => date(r.next_run_at) },
        { key: 'last_status', label: 'Último resultado' },
        { key: 'enabled', label: 'Ativo', render: (r) => (r.enabled ? 'Sim' : 'Não') },
      ]"
    >
      <template #actions="{ row }"
        ><button class="text-button" :disabled="busy" @click="confirm = row">
          {{ row.enabled ? 'Pausar' : 'Retomar' }}
        </button></template
      >
    </DataTable>
    <details>
      <summary>Últimas 10 tarefas em segundo plano</summary>
      <DataTable
        :rows="tasks"
        :columns="[
          { key: 'id', label: 'Tarefa' },
          { key: 'kind', label: 'Tipo' },
          { key: 'status', label: 'Status' },
          { key: 'error', label: 'Erro' },
        ]"
      />
    </details>
    <details>
      <summary>Últimas 10 entregas de email</summary>
      <DataTable
        :rows="emails"
        :columns="[
          { key: 'id', label: 'Entrega' },
          { key: 'subject', label: 'Assunto' },
          { key: 'status', label: 'Status' },
          { key: 'attempts', label: 'Tentativas' },
          { key: 'error', label: 'Erro' },
        ]"
      />
    </details>
    <AppDialog :open="!!confirm" title="Alterar agendamento?" @close="confirm = null"
      ><p>
        {{ confirm?.enabled ? 'Pausar' : 'Retomar' }} “{{ confirm?.name }}”? Ao retomar, o intervalo
        será contado a partir de agora.
      </p>
      <template #footer
        ><button class="button secondary" :disabled="busy" @click="confirm = null">Cancelar</button
        ><button class="button" :disabled="busy" @click="toggle">
          Confirmar agendamento
        </button></template
      ></AppDialog
    >
  </section>
</template>
