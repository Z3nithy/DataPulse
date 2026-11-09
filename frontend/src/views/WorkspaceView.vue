<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { allPages, api, docsUrl, format, post } from '@/services/api'
import DataTable from '@/components/DataTable.vue'
import MetricChart from '@/components/MetricChart.vue'
import QueryBuilder from '@/components/QueryBuilder.vue'
import DashboardOverview from '@/components/DashboardOverview.vue'
import Notification from '@/components/ui/Notification.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import FavoritesPanel from '@/components/FavoritesPanel.vue'
import OperationsPanel from '@/components/OperationsPanel.vue'
import OnboardingGuide from '@/components/OnboardingGuide.vue'
import { RefreshCw, Search, ArrowUpRight, UploadCloud, Plus, ShieldCheck } from '@lucide/vue'
import { useInterfaceStore } from '@/stores/interface'
import { rangeFilters } from '@/services/dateRange'
import { useReveal } from '@/composables/motion'

const route = useRoute()
const auth = useAuthStore()
const ui = useInterfaceStore()
const section = computed(() => route.meta.section)
const root = ref(null)
useReveal(root, () => section.value)
const localSearch = ref(String(route.query.search || ''))
const confirmation = ref(null)
watch(
  () => route.query.search,
  (value) => {
    localSearch.value = String(value || '')
  },
)
const visibleRows = computed(() => {
  if (!localSearch.value) return rows.value
  const candidates =
    { sources: sources.value, datasets: datasets.value, kpis: kpis.value }[section.value] ||
    rows.value
  return candidates.filter((row) =>
    JSON.stringify(row)
      .toLocaleLowerCase('pt-BR')
      .includes(localSearch.value.toLocaleLowerCase('pt-BR')),
  )
})
const busy = ref(false)
const error = ref('')
const notice = ref('')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const sources = ref([])
const datasets = ref([])
const kpis = ref([])
const summary = ref(null)
const result = ref(null)
const trend = ref(null)
watch(
  () => ui.range,
  () => {
    result.value = null
    trend.value = null
    notice.value = ''
  },
)
const selectedFile = ref(null)
const backgroundImport = ref(true)
const workerStatus = ref(null)
let jobPolling
let disposed = false
const selectedDataset = ref(null)
const preview = ref(null)
const auditRows = ref([])
const query = ref(freshQuery())
const favoriteQuery = computed(() => ({
  ...query.value,
  filters: [
    ...query.value.filters,
    ...(['analytics', 'trends'].includes(section.value)
      ? rangeFilters(query.value.date_field, ui.range)
      : []),
  ],
}))
function selectFavorite(value) {
  query.value = value
  if (section.value === 'kpis') {
    query.value.group_by = []
    query.value.date_field = null
  }
  ui.range = { from: '', to: '' }
  result.value = null
  trend.value = null
  notice.value =
    section.value === 'kpis'
      ? 'Favorito carregado como consulta escalar para KPI, sem agrupamentos. Os filtros foram preservados.'
      : 'Favorito carregado. Revise e execute a consulta.'
}
const sourceForm = ref({ name: '', kind: 'csv', url: '', credential_env: '' })
const datasetForm = ref({ name: '', description: '', source_id: null, columns: [] })
const kpiForm = ref({ name: '', target: null })
const reportName = ref('')
const alertForm = ref({ name: '', kpi_id: null, operator: 'gt', threshold: 0, enabled: true })
const editing = ref(null)
const memberForm = ref({ name: '', username: '', email: '', password: '' })
const demoAccount = ref(null)
const passwordForm = ref({ current_password: '', new_password: '' })
const profileForm = ref({ username: auth.user.username, email: auth.user.email || '' })
const temporaryPassword = ref(null)
let loadGeneration = 0
const paths = {
  sources: '/sources',
  datasets: '/datasets',
  ingestion: '/ingestion/jobs',
  kpis: '/kpis',
  insights: '/insights',
  reports: '/reports',
  alerts: '/alerts',
  settings: '/users',
}
const titles = {
  dashboard: ['Visao geral', 'Todos os seus dados. Uma nova perspectiva.'],
  sources: ['Fontes de dados', 'Organize as conexoes que alimentam suas decisoes.'],
  ingestion: ['Importar e processar', 'Da origem ao insight, com qualidade e rastreabilidade.'],
  datasets: ['Seus datasets', 'Dados estruturados, padronizados e prontos para explorar.'],
  analytics: ['Central de analises', 'Transforme perguntas em respostas baseadas em dados.'],
  kpis: ['Indicadores de desempenho', 'Acompanhe o que realmente importa para o negocio.'],
  trends: ['Analise de tendencias', 'Entenda como seus resultados evoluem ao longo do tempo.'],
  insights: ['Insights inteligentes', 'Sinais estatisticos reais. Sem previsoes inventadas.'],
  reports: ['Relatorios', 'Salve resultados e compartilhe decisoes bem informadas.'],
  alerts: ['Central de alertas', 'Monitore limites e identifique o que precisa de atencao.'],
  settings: ['Configuracoes', 'Gerencie sua equipe, permissoes e auditoria.'],
}
const columns = computed(
  () =>
    ({
      sources: [
        { key: 'name', label: 'Fonte' },
        { key: 'kind', label: 'Formato' },
        { key: 'url', label: 'Endpoint' },
      ],
      datasets: [
        { key: 'name', label: 'Dataset' },
        { key: 'record_count', label: 'Registros' },
        {
          key: 'schema',
          label: 'Esquema',
          render: (r) =>
            r.schema.map((c) => `${c.name} (${c.kind})`).join(', ') ||
            'Inferido na primeira importacao',
        },
      ],
      ingestion: [
        { key: 'id', label: 'Job' },
        { key: 'filename', label: 'Origem' },
        { key: 'status', label: 'Status' },
        { key: 'imported_rows', label: 'Importados' },
        { key: 'duplicate_rows', label: 'Duplicados' },
        { key: 'rejected_rows', label: 'Rejeitados' },
      ],
      kpis: [
        { key: 'name', label: 'Indicador' },
        { key: 'value', label: 'Valor atual' },
        { key: 'target', label: 'Meta' },
        {
          key: 'query',
          label: 'Calculo',
          render: (r) => `${r.query.aggregation} ${r.query.field || 'registros'}`,
        },
      ],
      insights: [
        { key: 'title', label: 'Insight' },
        { key: 'dataset_id', label: 'Dataset' },
        {
          key: 'details',
          label: 'Evidencias',
          render: (r) =>
            `${r.details.anomaly_count} anomalias / ${r.details.sample_size} valores. Media: ${format(r.details.mean)}. Regra: |z| > 3.`,
        },
      ],
      reports: [
        { key: 'name', label: 'Relatorio' },
        {
          key: 'created_at',
          label: 'Gerado em',
          render: (r) => new Date(r.created_at).toLocaleString('pt-BR'),
        },
        { key: 'result', label: 'Resultado', render: (r) => format(r.result.value) },
      ],
      alerts: [
        { key: 'name', label: 'Alerta' },
        {
          key: 'threshold',
          label: 'Condicao',
          render: (r) => `${r.operator} ${format(r.threshold)}`,
        },
        { key: 'last_value', label: 'Ultimo valor' },
        {
          key: 'triggered',
          label: 'Status',
          render: (r) =>
            !r.enabled ? 'Desativado' : r.triggered ? 'Limite atingido' : 'Dentro do limite',
        },
      ],
    })[section.value] || [],
)

function freshQuery() {
  return {
    dataset_id: null,
    aggregation: 'count',
    field: null,
    group_by: [],
    date_field: null,
    period: 'month',
    filters: [],
  }
}

function showError(exc) {
  const details = Array.isArray(exc.details)
    ? exc.details.map((d) => d.message).join('; ')
    : exc.details?.job
      ? exc.details.job.errors.map((e) => e.message).join('; ')
      : ''
  error.value = `${exc.message}${details ? `: ${details}` : ''}${exc.requestId ? ` (ID: ${exc.requestId})` : ''}`
}

async function load() {
  const generation = ++loadGeneration
  const currentSection = section.value
  const path = paths[currentSection]
  busy.value = true
  error.value = ''
  try {
    const primary =
      currentSection === 'dashboard'
        ? api('/analytics/summary')
        : path && (currentSection !== 'settings' || auth.isAdmin)
          ? api(`${path}?page=${page.value}&page_size=${pageSize}`)
          : Promise.resolve(null)
    const [sourceData, datasetData, kpiData, response, audit, operationStatus, demoStatus] =
      await Promise.all([
        allPages('/sources'),
        allPages('/datasets'),
        allPages('/kpis'),
        primary,
        currentSection === 'settings' && auth.isAdmin
          ? api('/audit?page_size=10')
          : Promise.resolve(null),
        currentSection === 'ingestion' ? api('/operations/status') : Promise.resolve(null),
        currentSection === 'settings' && auth.isAdmin ? api('/users/demo') : Promise.resolve(null),
      ])
    if (generation !== loadGeneration) return
    sources.value = sourceData
    datasets.value = datasetData
    kpis.value = kpiData
    if (currentSection === 'dashboard') {
      summary.value = response.data
    } else if (response) {
      rows.value = response.data
      total.value = response.meta.total
      if (currentSection === 'ingestion' && preview.value?.id) {
        preview.value = rows.value.find((job) => job.id === preview.value.id) || preview.value
      }
    }
    if (audit) auditRows.value = audit.data
    if (operationStatus) workerStatus.value = operationStatus.data
    if (demoStatus) demoAccount.value = demoStatus.data
  } catch (exc) {
    if (generation === loadGeneration) showError(exc)
  } finally {
    if (generation === loadGeneration) busy.value = false
  }
}
async function pollJobs() {
  if (
    !disposed &&
    !document.hidden &&
    section.value === 'ingestion' &&
    !busy.value &&
    rows.value.some((row) => ['queued', 'processing'].includes(row.status))
  )
    await load()
  if (!disposed) jobPolling = setTimeout(pollJobs, 4000)
}
onMounted(pollJobs)
onBeforeUnmount(() => {
  disposed = true
  loadGeneration++
  clearTimeout(jobPolling)
})
watch(
  section,
  () => {
    page.value = 1
    rows.value = []
    total.value = 0
    notice.value = ''
    result.value = null
    trend.value = null
    preview.value = null
    cancelEdit()
    selectedFile.value = null
    selectedDataset.value = null
    memberForm.value = { name: '', username: '', email: '', password: '' }
    load()
  },
  { immediate: true },
)

async function act(action, message) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await action()
    notice.value = message
    await load()
  } catch (exc) {
    if (exc.details?.job) {
      preview.value = exc.details.job
      await load()
    }
    showError(exc)
  } finally {
    busy.value = false
  }
}

async function createSource() {
  await act(async () => {
    const body = {
      ...sourceForm.value,
      url: sourceForm.value.kind === 'api' ? sourceForm.value.url : null,
      credential_env:
        sourceForm.value.kind === 'api' ? sourceForm.value.credential_env || null : null,
    }
    if (editing.value)
      await api(`/sources/${editing.value}`, { method: 'PATCH', body: JSON.stringify(body) })
    else await post('/sources', body)
    editing.value = null
    sourceForm.value = { name: '', kind: 'csv', url: '', credential_env: '' }
  }, 'Fonte salva.')
}

async function createDataset() {
  await act(async () => {
    if (editing.value) {
      const { name, description, source_id } = datasetForm.value
      await api(`/datasets/${editing.value}`, {
        method: 'PATCH',
        body: JSON.stringify({ name, description, source_id }),
      })
    } else await post('/datasets', datasetForm.value)
    editing.value = null
    datasetForm.value = { name: '', description: '', source_id: null, columns: [] }
  }, 'Dataset salvo. O esquema existente foi preservado.')
}

async function importFile() {
  preview.value = null
  await act(
    async () => {
      const form = new FormData()
      form.append('background', String(backgroundImport.value))
      form.append('dataset_id', selectedDataset.value)
      if (selectedFile.value) form.append('file', selectedFile.value)
      const response = await api('/ingestion/import', { method: 'POST', body: form })
      preview.value = response.data
    },
    backgroundImport.value
      ? 'Importação enfileirada. Pode navegar; o histórico será atualizado e você receberá uma notificação ao concluir.'
      : 'Processamento concluido. Consulte o resultado e eventuais rejeicoes abaixo.',
  )
}

async function runQuery() {
  const rangeKey = JSON.stringify(ui.range)
  function verifyRange() {
    if (JSON.stringify(ui.range) !== rangeKey)
      throw new Error(
        'O período mudou durante a consulta. Execute novamente para atualizar os resultados.',
      )
  }
  result.value = null
  trend.value = null
  await act(async () => {
    if (section.value === 'trends') {
      const params = new URLSearchParams(
        Object.fromEntries(
          Object.entries(query.value).filter(
            ([key, value]) =>
              ['dataset_id', 'field', 'date_field', 'aggregation', 'period'].includes(key) &&
              value !== null,
          ),
        ),
      )
      if (ui.range.from || ui.range.to) {
        const response = await post('/analytics/query', {
          ...query.value,
          filters: rangeFilters(query.value.date_field, ui.range),
        })
        verifyRange()
        trend.value = { series: response.data.groups, ...response.data.comparison }
      } else {
        const response = await api(`/analytics/trends?${params}`)
        verifyRange()
        trend.value = response.data
      }
      result.value = null
    } else {
      const response = await post('/analytics/query', {
        ...query.value,
        filters: [...query.value.filters, ...rangeFilters(query.value.date_field, ui.range)],
      })
      verifyRange()
      result.value = response.data
      trend.value = null
    }
  }, 'Consulta executada com dados reais.')
}

async function createKpi() {
  await act(async () => {
    const body = { ...kpiForm.value, query: query.value }
    if (editing.value)
      await api(`/kpis/${editing.value}`, { method: 'PATCH', body: JSON.stringify(body) })
    else await post('/kpis', body)
    cancelEdit()
  }, 'KPI salvo e alertas atualizados.')
}

function editItem(row) {
  editing.value = row.id
  if (section.value === 'sources')
    sourceForm.value = {
      name: row.name,
      kind: row.kind,
      url: row.url || '',
      credential_env: row.credential_env || '',
    }
  if (section.value === 'datasets')
    datasetForm.value = {
      name: row.name,
      description: row.description,
      source_id: row.source_id,
      columns: [],
    }
  if (section.value === 'kpis') {
    kpiForm.value = { name: row.name, target: row.target }
    query.value = {
      ...row.query,
      filters: row.query.filters.map((f) => ({ ...f })),
      group_by: [...row.query.group_by],
    }
  }
  globalThis.scrollTo({ top: 0, behavior: 'smooth' })
}
function cancelEdit() {
  editing.value = null
  sourceForm.value = { name: '', kind: 'csv', url: '', credential_env: '' }
  datasetForm.value = { name: '', description: '', source_id: null, columns: [] }
  kpiForm.value = { name: '', target: null }
  query.value = freshQuery()
}
async function createReport() {
  await act(
    () => post('/reports', { name: reportName.value, query: query.value }),
    'Relatorio gerado e salvo como snapshot.',
  )
}
async function createAlert() {
  await act(() => post('/alerts', alertForm.value), 'Alerta criado e avaliado.')
}
async function download(report) {
  await act(async () => {
    const blob = await api(`/reports/${report.id}/export`, { download: true })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `datapulse-report-${report.id}.csv`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }, 'Relatorio exportado.')
}
async function inspectDataset(dataset) {
  await act(async () => {
    preview.value = { dataset, ...(await api(`/datasets/${dataset.id}/records?page_size=20`)) }
  }, 'Previa dos primeiros 20 registros.')
}
async function jobDetails(job) {
  await act(async () => {
    preview.value = (await api(`/ingestion/jobs/${job.id}`)).data
  }, 'Detalhes da importacao carregados.')
}
async function saveUser(user) {
  confirmation.value = {
    title: 'Confirmar alteração de acesso',
    message: `Salvar o papel ${user.role} e o acesso ${user.active ? 'ativo' : 'desativado'} de ${user.name}? A alteração afeta imediatamente as permissões desta conta.`,
    action: () => commitUser(user),
  }
}
async function commitUser(user) {
  await act(
    () =>
      api(`/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ role: user.role, active: user.active }),
      }),
    'Permissoes atualizadas.',
  )
}
async function createMember() {
  await act(async () => {
    await post('/users', memberForm.value)
    memberForm.value = { name: '', username: '', email: '', password: '' }
  }, 'Membro criado como leitor. Ajuste as permissoes na lista da equipe.')
}
async function createDemoAccount() {
  await act(
    () => post('/users/demo', {}),
    'Conta pública criada. As credenciais já estão disponíveis no GUIA da tela de login.',
  )
}
function confirmDemoDataRestore() {
  confirmation.value = {
    title: 'Restaurar dados de demonstração?',
    message:
      'Os registros do dataset sintético “Vendas de demonstração” serão substituídos pelos dados de exemplo. Outros datasets, fontes, relatórios e dados do workspace não serão removidos.',
    action: restoreDemoData,
  }
}
async function restoreDemoData() {
  let restoredRecords = 0
  await act(async () => {
    const response = await post('/users/demo/restore-data', {})
    restoredRecords = response.data.records
  }, '')
  notice.value = `${restoredRecords} registros sintéticos restaurados. Os demais dados do workspace foram preservados.`
}
async function saveProfile() {
  await act(async () => {
    const response = await api('/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify({
        username: profileForm.value.username,
        email: profileForm.value.email || null,
      }),
    })
    auth.user = response.data
  }, 'Perfil atualizado.')
}
async function resetUserPassword(row) {
  confirmation.value = {
    title: 'Redefinir senha do membro?',
    message: `Uma senha provisória será gerada para ${row.name}. As sessões existentes serão encerradas; copie a senha exibida uma única vez e compartilhe-a por um canal seguro. Oriente o membro a alterá-la ao entrar.`,
    action: async () => {
      await act(async () => {
        const response = await post(`/users/${row.id}/password-reset`, {})
        temporaryPassword.value = {
          username: row.username,
          password: response.data.temporary_password,
        }
      }, 'Senha provisória gerada. Ela será exibida somente nesta janela.')
    },
  }
}
async function changePassword() {
  await act(async () => {
    const response = await post('/auth/password', passwordForm.value)
    auth.replaceToken(response.data.access_token)
    passwordForm.value = { current_password: '', new_password: '' }
  }, 'Senha atualizada. As outras sessoes foram encerradas.')
}
async function toggleAlert(alert) {
  confirmation.value = {
    title: alert.enabled ? 'Desativar alerta?' : 'Ativar alerta?',
    message: `A regra “${alert.name}” será ${alert.enabled ? 'desativada e deixará de monitorar o KPI' : 'ativada e avaliada com o valor atual do KPI'}.`,
    action: () => commitAlert(alert),
  }
}
async function commitAlert(alert) {
  await act(
    () =>
      api(`/alerts/${alert.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: alert.name,
          kpi_id: alert.kpi_id,
          operator: alert.operator,
          threshold: alert.threshold,
          enabled: !alert.enabled,
        }),
      }),
    'Alerta atualizado.',
  )
}
async function changePage(delta) {
  page.value += delta
  await load()
}
async function confirmAction() {
  const action = confirmation.value?.action
  confirmation.value = null
  await action?.()
}
</script>

<template>
  <section ref="root" class="page-content">
    <div class="page-heading" data-reveal>
      <div>
        <p class="eyebrow"><span class="status-dot" /> DATAPULSE INTELLIGENCE</p>
        <h1>{{ section === 'dashboard' ? 'Seu negócio, em perspectiva.' : titles[section][0] }}</h1>
        <p class="muted">
          {{
            section === 'dashboard'
              ? 'Conecte os pontos. Descubra padrões. Decida com confiança.'
              : titles[section][1]
          }}
        </p>
      </div>
      <div class="page-actions">
        <button class="button secondary" :disabled="busy" @click="load">
          <RefreshCw :size="15" :class="{ spin: busy }" />Atualizar dados</button
        ><RouterLink v-if="section === 'dashboard' && auth.canEdit" class="button" to="/ingestion"
          ><Plus :size="16" /> Importar dados</RouterLink
        >
      </div>
    </div>
    <Notification v-if="error" :message="error" kind="error" @dismiss="error = ''" />
    <Notification v-if="notice" :message="notice" kind="success" @dismiss="notice = ''" />
    <LoadingState v-if="busy" :skeleton="section === 'dashboard' && !summary" />
    <div v-if="editing" class="message info">
      Editando registro #{{ editing }}.
      <button class="text-button" :disabled="busy" @click="cancelEdit">Cancelar edicao</button>
    </div>

    <OnboardingGuide v-if="section === 'dashboard' && summary" :summary="summary" />
    <DashboardOverview
      v-if="section === 'dashboard' && summary"
      :summary="summary"
      :datasets="datasets"
    />

    <FavoritesPanel
      v-if="['analytics', 'kpis', 'reports'].includes(section)"
      :query="favoriteQuery"
      @select="selectFavorite"
    />
    <div
      v-if="['analytics', 'trends', 'kpis', 'reports'].includes(section)"
      class="panel query-panel"
      :data-tour="
        ['analytics', 'trends', 'kpis', 'reports'].includes(section) ? section : undefined
      "
    >
      <h2>
        {{
          section === 'dashboard'
            ? 'Evolucao e distribuicao'
            : section === 'kpis'
              ? 'Criar indicador'
              : section === 'reports'
                ? 'Gerar relatorio'
                : 'Construtor de consultas'
        }}
      </h2>
      <p class="query-hint">
        <ShieldCheck :size="15" /> Consultas estruturadas sobre seus dados. Sem execução de SQL
        livre.
      </p>
      <p
        v-if="(ui.range.from || ui.range.to) && ['analytics', 'trends'].includes(section)"
        class="muted small"
      >
        O período do header será aplicado às consultas com coluna de data. Execute a análise após
        alterar o período.
      </p>
      <p v-if="['kpis', 'reports'].includes(section)" class="muted small">
        O período do header não altera indicadores ou relatórios. Configure os filtros da consulta
        abaixo.
      </p>
      <form
        :aria-busy="busy"
        @submit.prevent="
          section === 'kpis' ? createKpi() : section === 'reports' ? createReport() : runQuery()
        "
      >
        <div v-if="['kpis', 'reports'].includes(section)" class="form-grid">
          <label
            >Nome<input
              v-if="section === 'kpis'"
              v-model="kpiForm.name"
              required
              minlength="2"
              maxlength="100"
              :disabled="!auth.canEdit" /><input
              v-else
              v-model="reportName"
              required
              minlength="2"
              maxlength="100"
              :disabled="!auth.canEdit"
          /></label>
          <label v-if="section === 'kpis'"
            >Meta (opcional)<input
              v-model.number="kpiForm.target"
              type="number"
              step="any"
              @change="kpiForm.target = kpiForm.target === '' ? null : kpiForm.target"
          /></label>
        </div>
        <QueryBuilder
          v-model="query"
          :datasets="datasets"
          :scalar="section === 'kpis'"
          :temporal="section === 'trends'"
        />
        <button
          class="button"
          :disabled="
            busy || !query.dataset_id || (['kpis', 'reports'].includes(section) && !auth.canEdit)
          "
        >
          {{
            section === 'kpis'
              ? 'Salvar KPI'
              : section === 'reports'
                ? 'Gerar relatorio'
                : 'Executar analise'
          }}
        </button>
      </form>
      <template v-if="result">
        <div class="result-metrics">
          <span
            >Resultado <strong>{{ format(result.value) }}</strong></span
          ><span
            >Registros <strong>{{ format(result.count) }}</strong></span
          ><span v-for="(value, key) in result.statistics" :key="key"
            >{{ key }} <strong>{{ format(value) }}</strong></span
          >
        </div>
        <div v-if="result.comparison" class="result-metrics">
          <span
            >Periodo anterior <strong>{{ format(result.comparison.previous) }}</strong></span
          ><span
            >Periodo atual <strong>{{ format(result.comparison.current) }}</strong></span
          ><span
            >Crescimento
            <strong>{{
              result.comparison.growth_percent === null
                ? 'Indisponivel'
                : `${format(result.comparison.growth_percent)}%`
            }}</strong></span
          >
          <p class="muted small">{{ result.comparison.comparison }}</p>
        </div>
        <MetricChart :groups="result.groups" />
        <DataTable
          v-if="result.groups.length"
          :rows="result.groups"
          :columns="[
            { key: 'group', label: 'Grupo' },
            { key: 'count', label: 'Registros' },
            { key: 'value', label: 'Valor' },
          ]"
        />
      </template>
      <template v-if="trend">
        <div class="result-metrics">
          <span
            >Periodo atual <strong>{{ format(trend.current) }}</strong></span
          ><span
            >Periodo anterior <strong>{{ format(trend.previous) }}</strong></span
          ><span
            >Crescimento
            <strong>{{
              trend.growth_percent === null ? 'Indisponivel' : `${format(trend.growth_percent)}%`
            }}</strong></span
          ><span
            >Direcao
            <strong>{{
              {
                up: 'Alta',
                down: 'Queda',
                stable: 'Estavel',
                insufficient_data: 'Dados insuficientes',
              }[trend.direction]
            }}</strong></span
          >
        </div>
        <MetricChart :groups="trend.series" title="Evolucao historica" />
        <p class="muted small">{{ trend.comparison }}</p>
      </template>
    </div>

    <div v-if="section === 'sources' && auth.canEdit" class="panel" data-tour="sources">
      <h2>{{ editing ? 'Editar fonte' : 'Adicionar fonte' }}</h2>
      <form @submit.prevent="createSource">
        <div class="form-grid">
          <label
            >Nome<input
              v-model="sourceForm.name"
              required
              minlength="2"
              maxlength="100"
              placeholder="Ex.: Vendas mensais" /></label
          ><label
            >Formato<select v-model="sourceForm.kind">
              <option value="csv">CSV</option>
              <option value="excel">Excel</option>
              <option value="json">JSON</option>
              <option value="api">API HTTPS</option>
            </select></label
          ><template v-if="sourceForm.kind === 'api'"
            ><label
              >URL autorizada<input
                v-model="sourceForm.url"
                type="url"
                required
                placeholder="https://api.exemplo.com/dados" /></label
            ><label
              >Variavel da credencial (opcional)<input
                v-model="sourceForm.credential_env"
                placeholder="DATAPULSE_API_VENDAS"
                pattern="DATAPULSE_API_[A-Z0-9_]+" /></label
          ></template>
        </div>
        <p v-if="sourceForm.kind === 'api'" class="muted small">
          O administrador do servidor precisa autorizar o host em API_ALLOWED_HOSTS. Informe apenas
          o nome da variavel, nunca o segredo.
        </p>
        <button class="button" :disabled="busy">
          {{ editing ? 'Salvar fonte' : 'Cadastrar fonte' }}
        </button>
      </form>
    </div>

    <div v-if="section === 'datasets' && auth.canEdit" class="panel" data-tour="datasets">
      <h2>{{ editing ? 'Editar dataset' : 'Criar dataset' }}</h2>
      <form @submit.prevent="createDataset">
        <div class="form-grid">
          <label
            >Nome<input v-model="datasetForm.name" required minlength="2" maxlength="100" /></label
          ><label
            >Fonte<select v-model="datasetForm.source_id">
              <option :value="null">Upload sem fonte vinculada</option>
              <option v-for="source in sources" :key="source.id" :value="source.id">
                {{ source.name }}
              </option>
            </select></label
          ><label>Descricao<input v-model="datasetForm.description" maxlength="2000" /></label>
        </div>
        <details v-if="!editing">
          <summary>Definir esquema manualmente (opcional)</summary>
          <div v-for="(column, index) in datasetForm.columns" :key="index" class="filter-row">
            <label>Nome da coluna<input v-model="column.name" required maxlength="100" /></label
            ><label
              >Tipo<select v-model="column.kind">
                <option value="string">Texto</option>
                <option value="number">Numero</option>
                <option value="date">Data ISO</option>
                <option value="boolean">Booleano</option>
              </select></label
            ><label class="checkbox"
              ><input v-model="column.required" type="checkbox" /> Obrigatoria</label
            ><button
              type="button"
              class="button secondary"
              @click="datasetForm.columns.splice(index, 1)"
            >
              Remover
            </button>
          </div>
          <button
            type="button"
            class="button secondary small"
            :disabled="datasetForm.columns.length >= 100"
            @click="datasetForm.columns.push({ name: '', kind: 'string', required: false })"
          >
            + Coluna
          </button>
        </details>
        <p class="muted small">
          Sem esquema manual, os tipos sao inferidos na primeira importacao. O esquema e preservado
          nas edicoes. Datas devem usar ISO (AAAA-MM-DD).
        </p>
        <button class="button" :disabled="busy">
          {{ editing ? 'Salvar dataset' : 'Criar dataset' }}
        </button>
      </form>
    </div>

    <div v-if="section === 'ingestion' && auth.canEdit" class="panel" data-tour="ingestion">
      <h2><UploadCloud :size="20" /> Nova importação</h2>
      <form @submit.prevent="importFile">
        <div class="form-grid">
          <label
            >Dataset de destino<select v-model="selectedDataset" required>
              <option :value="null" disabled>Selecione</option>
              <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
                {{ dataset.name }}
              </option>
            </select></label
          ><label class="upload"
            >Arquivo CSV, Excel ou JSON<input
              type="file"
              accept=".csv,.json,.xlsx,.xls"
              @change="selectedFile = $event.target.files[0] || null"
          /></label>
        </div>
        <p class="muted small">
          Ate 5 MB e 10.000 registros por dataset. Espacos sao removidos e duplicados ignorados. Sem
          arquivo, a fonte API vinculada sera consultada.
        </p>
        <label class="checkbox"
          ><input v-model="backgroundImport" type="checkbox" /> Processar em segundo plano</label
        >
        <p
          v-if="backgroundImport && workerStatus && !workerStatus.worker_online"
          class="message warning"
        >
          Worker offline: a importação ficará na fila até o worker do servidor iniciar.
        </p>
        <p v-if="!backgroundImport" class="muted small">
          Modo síncrono: aguarde a conclusão antes de sair da página.
        </p>
        <button class="button" :disabled="busy || !selectedDataset">Importar e validar</button>
      </form>
    </div>

    <div v-if="section === 'alerts' && auth.canEdit" class="panel" data-tour="alerts">
      <h2>Criar regra de alerta</h2>
      <form @submit.prevent="createAlert">
        <div class="form-grid">
          <label
            >Nome<input v-model="alertForm.name" minlength="2" maxlength="100" required /></label
          ><label
            >KPI<select v-model="alertForm.kpi_id" required>
              <option :value="null" disabled>Selecione</option>
              <option v-for="kpi in kpis" :key="kpi.id" :value="kpi.id">{{ kpi.name }}</option>
            </select></label
          ><label
            >Condicao<select v-model="alertForm.operator">
              <option value="gt">Maior que</option>
              <option value="gte">Maior ou igual</option>
              <option value="lt">Menor que</option>
              <option value="lte">Menor ou igual</option>
              <option value="eq">Igual a</option>
            </select></label
          ><label
            >Limite<input v-model.number="alertForm.threshold" type="number" step="any" required
          /></label>
        </div>
        <p class="muted small">
          Regras avaliadas na criacao, alteracao e em cada importacao do dataset. Alertas sao
          internos. Quando SMTP está habilitado, um email é enfileirado ao atingir o limite.
        </p>
        <button class="button" :disabled="busy">Criar alerta</button>
      </form>
    </div>

    <div v-if="section === 'insights'" class="message info">
      Deteccao estatistica por |z-score| &gt; 3 com pelo menos 5 valores. Os insights sao
      atualizados apos importacoes. Ausencia de insights nao significa ausencia de riscos. Nao
      utilizamos IA ou previsoes nesta versao.
    </div>

    <div
      v-if="paths[section] && section !== 'settings'"
      class="panel"
      :data-tour="section === 'insights' ? 'insights' : undefined"
    >
      <div class="panel-heading">
        <h2>{{ section === 'ingestion' ? 'Historico de processamento' : 'Registros' }}</h2>
        <span class="muted small">{{ total }} no total</span>
      </div>
      <label class="search-input table-search"
        ><Search :size="16" /><input
          v-model="localSearch"
          type="search"
          :placeholder="
            ['sources', 'datasets', 'kpis'].includes(section)
              ? 'Buscar em todos os registros...'
              : 'Buscar nesta página...'
          "
          aria-label="Buscar registros"
        /><kbd v-if="localSearch">{{ visibleRows.length }}</kbd></label
      >
      <DataTable :rows="visibleRows" :columns="columns" :caption="titles[section][0]"
        ><template
          v-if="['datasets', 'sources', 'kpis', 'ingestion', 'reports', 'alerts'].includes(section)"
          #actions="{ row }"
          ><button
            v-if="['sources', 'datasets', 'kpis'].includes(section) && auth.canEdit"
            class="text-button"
            :disabled="busy"
            @click="editItem(row)"
          >
            Editar</button
          ><button
            v-if="section === 'datasets'"
            class="text-button"
            :disabled="busy"
            @click="inspectDataset(row)"
          >
            Ver dados</button
          ><button
            v-if="section === 'ingestion'"
            class="text-button"
            :disabled="busy"
            @click="jobDetails(row)"
          >
            Detalhes</button
          ><button
            v-if="section === 'reports'"
            class="text-button"
            :disabled="busy"
            @click="download(row)"
          >
            Exportar CSV</button
          ><button
            v-if="section === 'alerts' && auth.canEdit"
            class="text-button"
            :disabled="busy"
            @click="toggleAlert(row)"
          >
            {{ row.enabled ? 'Desativar' : 'Ativar' }}
          </button></template
        ></DataTable
      >
    </div>

    <div v-if="preview" class="panel">
      <div class="panel-heading">
        <h2>Detalhes</h2>
        <button class="text-button" @click="preview = null">Fechar</button>
      </div>
      <template v-if="preview.dataset"
        ><DataTable
          :rows="preview.data.map((record) => ({ id: record.id, ...record.data }))"
          :columns="
            preview.dataset.schema.map((column) => ({ key: column.name, label: column.name }))
          "
        />
        <p class="muted small">
          {{ preview.meta.total }} registros no dataset. Previa limitada aos primeiros 20; use
          analises para consultar o conjunto.
        </p></template
      ><template v-else
        ><p>
          Job #{{ preview.id }}: <strong>{{ preview.status }}</strong> —
          {{ preview.imported_rows }} importados, {{ preview.duplicate_rows }} duplicados,
          {{ preview.rejected_rows }} rejeitados.
        </p>
        <ul v-if="preview.errors?.length" class="error-list">
          <li v-for="(item, index) in preview.errors" :key="index">
            {{ item.row ? `Linha ${item.row}: ` : '' }}{{ item.message }}
          </li>
        </ul>
        <p v-else class="muted">Nenhum erro de validacao registrado.</p></template
      >
    </div>

    <div v-if="section === 'settings' && auth.isAdmin" class="panel">
      <h2>Adicionar membro da equipe</h2>
      <form @submit.prevent="createMember">
        <div class="form-grid">
          <label
            >Nome<input
              v-model="memberForm.name"
              required
              minlength="2"
              maxlength="100"
              autocomplete="off" /></label
          ><label
            >Usuário<input
              v-model="memberForm.username"
              required
              minlength="3"
              maxlength="32"
              pattern="[A-Za-z0-9._-]+"
              autocomplete="off" /></label
          ><label
            >Email de contato (opcional)<input
              v-model="memberForm.email"
              type="email"
              maxlength="254"
              autocomplete="off" /></label
          ><label
            >Senha inicial<input
              v-model="memberForm.password"
              required
              type="password"
              minlength="10"
              maxlength="128"
              autocomplete="new-password"
          /></label>
        </div>
        <button class="button" :disabled="busy">Criar membro</button>
      </form>
    </div>
    <div v-if="section === 'settings' && auth.isAdmin && demoAccount" class="panel">
      <h2>Conta pública para demonstração</h2>
      <p class="muted small">
        Crie uma conta editora compartilhada. Depois de criada, o GUIA da tela de login mostra as
        credenciais para visitantes. Todos terão acesso aos mesmos dados deste workspace.
      </p>
      <p v-if="!demoAccount.enabled" class="muted">
        A criação está desabilitada. Configure <code>DEMO_MODE=true</code> no backend para liberar
        esta opção.
      </p>
      <template v-else-if="demoAccount.created">
        <p>
          <span class="badge">{{
            demoAccount.available ? 'Disponível no GUIA' : 'Indisponível'
          }}</span>
          <span v-if="demoAccount.username"> · usuário {{ demoAccount.username }}</span>
        </p>
        <p class="muted small">
          A restauração substitui somente os registros do dataset sintético “Vendas de
          demonstração”. Dados e relatórios dos outros datasets permanecem intactos.
        </p>
        <button class="button secondary" :disabled="busy" @click="confirmDemoDataRestore">
          Restaurar dados de demonstração
        </button>
        <p v-if="!demoAccount.active" class="muted small">
          Reative o acesso desta conta na lista da equipe para voltar a exibi-la no GUIA.
        </p>
        <p v-else-if="!demoAccount.available" class="muted small">
          As credenciais configuradas não correspondem à conta. Confira DEMO_USERNAME e
          DEMO_PASSWORD no backend.
        </p>
      </template>
      <template v-else>
        <p v-if="demoAccount.username" class="small">
          Usuário: <strong>{{ demoAccount.username }}</strong>
        </p>
        <button class="button" :disabled="busy" @click="createDemoAccount">
          Criar conta pública
        </button>
      </template>
    </div>
    <template v-if="section === 'settings'"
      ><div class="panel" data-tour="settings">
        <h2>Seu workspace</h2>
        <p>
          {{ auth.user.name }} · Usuário: {{ auth.user.username }}
          <template v-if="auth.user.email"> · {{ auth.user.email }}</template>
        </p>
        <p>
          Papel: <span class="badge">{{ auth.user.role }}</span>
        </p>
        <p class="muted">
          Os dados sao compartilhados pela equipe. Leitores consultam dados; editores cadastram e
          processam; administradores tambem gerenciam usuarios. Tokens expiram em 60 minutos.
        </p>
        <a :href="docsUrl" target="_blank" rel="noopener">Documentacao da API (Swagger)</a>
      </div>
      <div v-if="!auth.user.is_public_demo" class="panel">
        <h2>Meu perfil</h2>
        <p class="muted small">
          Atualize seu nome de usuário e o email de contato opcional. O nome de usuário é usado no
          login.
        </p>
        <form @submit.prevent="saveProfile">
          <div class="form-grid">
            <label
              >Usuário<input
                v-model="profileForm.username"
                required
                minlength="3"
                maxlength="32"
                pattern="[A-Za-z0-9._-]+"
                autocomplete="username"
            /></label>
            <label
              >Email de contato (opcional)<input
                v-model="profileForm.email"
                type="email"
                maxlength="254"
                autocomplete="email"
            /></label>
          </div>
          <button class="button" :disabled="busy">Salvar perfil</button>
        </form>
      </div>
      <div v-if="!auth.user.is_public_demo" class="panel">
        <h2>Alterar senha</h2>
        <p class="muted small">
          Use uma senha com pelo menos 10 caracteres. A alteracao encerra as outras sessoes da sua
          conta.
        </p>
        <form @submit.prevent="changePassword">
          <div class="form-grid">
            <label
              >Senha atual<input
                v-model="passwordForm.current_password"
                type="password"
                autocomplete="current-password"
                minlength="1"
                maxlength="128"
                required
            /></label>
            <label
              >Nova senha<input
                v-model="passwordForm.new_password"
                type="password"
                autocomplete="new-password"
                minlength="10"
                maxlength="128"
                required
            /></label>
          </div>
          <button class="button" :disabled="busy">Atualizar senha</button>
        </form>
      </div>
      <div v-if="auth.isAdmin" class="panel">
        <h2>Equipe</h2>
        <DataTable
          :rows="rows"
          :columns="[
            { key: 'name', label: 'Nome' },
            { key: 'username', label: 'Usuário' },
            { key: 'email', label: 'Email de contato' },
            { key: 'role', label: 'Papel' },
            { key: 'active', label: 'Ativo' },
          ]"
          ><template #role="{ row }"
            ><span v-if="row.is_public_demo" class="badge">Editor · conta pública</span>
            <select v-else v-model="row.role" :aria-label="`Papel de ${row.name}`">
              <option value="viewer">Leitor</option>
              <option value="editor">Editor</option>
              <option value="admin">Administrador</option>
            </select></template
          ><template #active="{ row }"
            ><input
              v-model="row.active"
              type="checkbox"
              :aria-label="`Acesso ativo de ${row.name}`" /></template
          ><template #actions="{ row }"
            ><button class="text-button" :disabled="busy" @click="saveUser(row)">Salvar</button>
            <button
              v-if="!row.is_public_demo && row.id !== auth.user.id"
              class="text-button"
              :disabled="busy"
              @click="resetUserPassword(row)"
            >
              Redefinir senha
            </button></template
          ></DataTable
        >
      </div>
      <div v-if="auth.isAdmin" class="panel">
        <h2>Auditoria recente</h2>
        <DataTable
          :rows="auditRows"
          :columns="[
            { key: 'user_id', label: 'Usuario' },
            { key: 'action', label: 'Acao' },
            { key: 'entity', label: 'Entidade' },
            { key: 'entity_id', label: 'Registro' },
            { key: 'created_at', label: 'Data' },
          ]"
        /></div
    ></template>
    <nav
      v-if="
        paths[section] &&
        !localSearch &&
        (section !== 'settings' || auth.isAdmin) &&
        total > pageSize
      "
      class="pagination"
      aria-label="Paginacao"
    >
      <button class="button secondary" :disabled="page === 1 || busy" @click="changePage(-1)">
        Anterior</button
      ><span>Pagina {{ page }} de {{ Math.ceil(total / pageSize) }}</span
      ><button
        class="button secondary"
        :disabled="page * pageSize >= total || busy"
        @click="changePage(1)"
      >
        Proxima
      </button>
    </nav>
    <OperationsPanel
      v-if="auth.isAdmin && ['settings', 'ingestion', 'reports'].includes(section)"
      :datasets="datasets"
      :initial-kind="section === 'reports' ? 'report' : 'import'"
      :sources="sources"
    />
    <AppDialog
      :open="!!confirmation"
      :title="confirmation?.title || 'Confirmar alteração'"
      @close="confirmation = null"
      ><p class="muted">{{ confirmation?.message }}</p>
      <template #footer
        ><button class="button secondary" @click="confirmation = null">Cancelar</button
        ><button class="button" @click="confirmAction">
          Confirmar alteração <ArrowUpRight :size="15" /></button></template
    ></AppDialog>
    <AppDialog
      :open="!!temporaryPassword"
      title="Senha provisória — copie agora"
      @close="temporaryPassword = null"
    >
      <p>
        Usuário: <strong>{{ temporaryPassword?.username }}</strong>
      </p>
      <p class="temporary-password">{{ temporaryPassword?.password }}</p>
      <p class="muted small">
        Esta senha não será exibida novamente. Compartilhe-a por um canal seguro e peça ao membro
        para alterá-la após entrar.
      </p>
      <template #footer>
        <button class="button" @click="temporaryPassword = null">Entendi e ocultar</button>
      </template>
    </AppDialog>
  </section>
</template>
