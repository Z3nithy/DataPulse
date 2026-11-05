<script setup>
import { computed, ref, watch } from 'vue'
import {
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Database,
  PlugZap,
  Layers3,
  Gauge,
  Sparkles,
  Bell,
  ChartNoAxesCombined,
  SlidersHorizontal,
  UploadCloud,
  ArrowRight,
  Clock3,
} from '@lucide/vue'
import { api, format, post } from '@/services/api'
import { useInterfaceStore } from '@/stores/interface'
import { rangeFilters } from '@/services/dateRange'
import { useReveal } from '@/composables/motion'
import MetricCard from './ui/MetricCard.vue'
import EmptyState from './ui/EmptyState.vue'
import LoadingState from './ui/LoadingState.vue'
import Notification from './ui/Notification.vue'
import MetricChart from './MetricChart.vue'
import DistributionChart from './DistributionChart.vue'
import DataTable from './DataTable.vue'
const props = defineProps({
  summary: { type: Object, required: true },
  datasets: { type: Array, required: true },
})
const ui = useInterfaceStore()
const root = ref(null)
const selected = ref(null)
const dateField = ref('')
const numberField = ref('')
const categoryField = ref('')
const period = ref('month')
const activeTab = ref('overview')
const result = ref(null)
const distribution = ref(null)
const busy = ref(false)
const error = ref('')
const insightCount = ref(null)
const countError = ref('')
const overviewTab = ref(null)
const activityTab = ref(null)
function switchTab(tab) {
  activeTab.value = tab
  const target = tab === 'overview' ? overviewTab : activityTab
  target.value?.focus()
}
const dataset = computed(() => props.datasets.find((item) => item.id === selected.value))
const dates = computed(() => dataset.value?.schema.filter((c) => c.kind === 'date') || [])
const numbers = computed(() => dataset.value?.schema.filter((c) => c.kind === 'number') || [])
const categories = computed(
  () => dataset.value?.schema.filter((c) => c.kind === 'string' || c.kind === 'boolean') || [],
)
const comparison = computed(() => result.value?.comparison)
let generation = 0
let countGeneration = 0
useReveal(root, () => props.summary)
watch(
  () => props.datasets,
  (items) => {
    if (!items.some((item) => item.id === selected.value))
      selected.value = items.find((item) => item.record_count > 0)?.id || items[0]?.id || null
  },
  { immediate: true },
)
watch(
  dataset,
  (current, previous) => {
    const changed = current?.id !== previous?.id
    if (changed || !dates.value.some((column) => column.name === dateField.value))
      dateField.value = dates.value[0]?.name || ''
    if (
      changed ||
      (!numbers.value.some((column) => column.name === numberField.value) &&
        numberField.value !== '')
    )
      numberField.value = numbers.value[0]?.name || ''
    if (changed || !categories.value.some((column) => column.name === categoryField.value))
      categoryField.value = categories.value[0]?.name || ''
  },
  { immediate: true },
)
watch(
  () => props.summary,
  async () => {
    const current = ++countGeneration
    insightCount.value = null
    countError.value = ''
    try {
      const response = await api('/insights?page_size=1')
      if (current === countGeneration) insightCount.value = response.meta.total
    } catch (exc) {
      if (current === countGeneration) countError.value = exc.message
    }
  },
  { immediate: true },
)
watch(
  [selected, dateField, numberField, categoryField, period, () => ui.range, () => props.summary],
  async () => {
    const current = ++generation
    error.value = ''
    result.value = null
    distribution.value = null
    if (!selected.value) {
      busy.value = false
      return
    }
    busy.value = true
    const filters = rangeFilters(dateField.value, ui.range)
    try {
      const [evolution, grouped] = await Promise.all([
        dateField.value
          ? post('/analytics/query', {
              dataset_id: selected.value,
              aggregation: numberField.value ? 'sum' : 'count',
              field: numberField.value || null,
              date_field: dateField.value,
              period: period.value,
              filters,
            })
          : Promise.resolve(null),
        categoryField.value
          ? post('/analytics/query', {
              dataset_id: selected.value,
              group_by: [categoryField.value],
              filters,
            })
          : Promise.resolve(null),
      ])
      if (current !== generation) return
      result.value = evolution?.data || null
      distribution.value = grouped?.data || null
    } catch (exc) {
      if (current === generation) error.value = exc.message
    } finally {
      if (current === generation) busy.value = false
    }
  },
  { immediate: true },
)
const jobs = computed(() => props.summary.recent_jobs)
const date = (value) =>
  value
    ? new Date(value).toLocaleString('pt-BR', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'Sem data'
const progress = (kpi) =>
  kpi.target > 0 && kpi.value !== null
    ? Math.max(0, Math.min(100, (kpi.value / kpi.target) * 100))
    : null
</script>
<template>
  <div ref="root" class="dashboard-overview">
    <div class="overview-toolbar" data-reveal>
      <div class="view-tabs" role="tablist" aria-label="Visualização do dashboard">
        <button
          id="overview-tab"
          ref="overviewTab"
          role="tab"
          aria-controls="overview-panel"
          :aria-selected="activeTab === 'overview'"
          :tabindex="activeTab === 'overview' ? 0 : -1"
          @click="activeTab = 'overview'"
          @keydown.right.prevent="switchTab('activity')"
          @keydown.left.prevent="switchTab('activity')"
          @keydown.home.prevent="switchTab('overview')"
          @keydown.end.prevent="switchTab('activity')"
        >
          <ChartNoAxesCombined :size="15" /> Visão geral</button
        ><button
          id="activity-tab"
          ref="activityTab"
          role="tab"
          aria-controls="activity-panel"
          :aria-selected="activeTab === 'activity'"
          :tabindex="activeTab === 'activity' ? 0 : -1"
          @click="activeTab = 'activity'"
          @keydown.left.prevent="switchTab('overview')"
          @keydown.right.prevent="switchTab('overview')"
          @keydown.home.prevent="switchTab('overview')"
          @keydown.end.prevent="switchTab('activity')"
        >
          Atividade recente
        </button>
      </div>
      <span class="live-status"><span class="status-dot" /> Dados do workspace</span>
    </div>
    <p class="scope-note" data-reveal>
      Indicadores históricos do workspace · o período selecionado filtra os gráficos abaixo.
    </p>
    <div class="metrics dashboard-metrics">
      <MetricCard
        label="Registros processados"
        :value="summary.records"
        note="Registros únicos armazenados"
        :icon="Database"
        to="/datasets"
      />
      <MetricCard
        label="Fontes de dados"
        :value="summary.sources"
        note="Cadastradas · sem teste de conexão"
        :icon="PlugZap"
        tone="cyan"
        to="/sources"
      />
      <MetricCard
        label="Datasets"
        :value="summary.datasets"
        note="Conjuntos disponíveis para análise"
        :icon="Layers3"
        tone="violet"
        to="/datasets"
      />
      <MetricCard
        label="KPIs monitorados"
        :value="summary.kpi_count"
        note="Indicadores personalizados"
        :icon="Gauge"
        tone="cyan"
        to="/kpis"
      />
      <MetricCard
        label="Insights gerados"
        :value="insightCount"
        note="Regras estatísticas · sem IA"
        :icon="Sparkles"
        tone="violet"
        to="/insights"
      />
      <MetricCard
        label="Alertas ativos"
        :value="summary.active_alerts"
        note="Regras habilitadas e acionadas"
        :icon="Bell"
        tone="amber"
        to="/alerts"
      />
    </div>
    <Notification
      v-if="countError"
      :message="`Não foi possível carregar o total de insights: ${countError}`"
      kind="error"
      @dismiss="countError = ''"
    />
    <div
      v-show="activeTab === 'overview'"
      id="overview-panel"
      role="tabpanel"
      aria-labelledby="overview-tab"
    >
      <div class="dashboard-filter" data-reveal>
        <div class="filter-label"><SlidersHorizontal :size="16" /><span>Explorar dados</span></div>
        <label class="sr-only" for="dashboard-dataset">Dataset do dashboard</label
        ><select id="dashboard-dataset" v-model="selected">
          <option :value="null" disabled>Selecione um dataset</option>
          <option v-for="item in datasets" :key="item.id" :value="item.id">
            {{ item.name }}
          </option></select
        ><label class="sr-only" for="dashboard-value">Métrica do gráfico</label
        ><select id="dashboard-value" v-model="numberField">
          <option value="">Contagem de registros</option>
          <option v-for="column in numbers" :key="column.name" :value="column.name">
            Soma de {{ column.name }}
          </option></select
        ><span class="badge">DADOS REAIS</span>
      </div>
      <Notification v-if="error" kind="error" :message="error" @dismiss="error = ''" />
      <LoadingState v-if="busy" />
      <div class="dashboard-charts">
        <section class="panel chart-card evolution-card" data-reveal>
          <div class="panel-heading">
            <div>
              <span class="eyebrow">PERFORMANCE</span>
              <h2>Evolução dos dados</h2>
            </div>
            <label class="sr-only" for="chart-period">Agrupamento temporal</label
            ><select id="chart-period" v-model="period" class="compact-select">
              <option value="day">Diário</option>
              <option value="week">Semanal</option>
              <option value="month">Mensal</option>
              <option value="year">Anual</option>
            </select>
          </div>
          <div class="chart-value">
            <strong>{{ format(result?.value) }}</strong
            ><span
              v-if="comparison?.growth_percent !== null && comparison?.growth_percent !== undefined"
              class="comparison-pill"
              :class="{ negative: comparison.growth_percent < 0 }"
              ><component
                :is="
                  comparison.growth_percent > 0
                    ? ArrowUpRight
                    : comparison.growth_percent < 0
                      ? ArrowDownRight
                      : Minus
                "
                :size="14"
              />{{ format(comparison.growth_percent) }}%</span
            ><small>{{ numberField ? `Soma de ${numberField}` : 'Contagem de registros' }}</small>
          </div>
          <label v-if="dates.length" class="chart-field"
            >Coluna de data<select v-model="dateField">
              <option v-for="column in dates" :key="column.name" :value="column.name">
                {{ column.name }}
              </option>
            </select></label
          >
          <MetricChart :groups="result?.groups || []" variant="area" title="Evolução dos dados" />
          <div class="chart-summary">
            <span><span class="legend-dot" />{{ numberField || 'Registros' }}</span
            ><small>{{
              comparison
                ? 'Comparação dos dois últimos períodos observados'
                : 'Selecione uma coluna de data para analisar a evolução'
            }}</small>
          </div>
        </section>
        <section class="panel chart-card" data-reveal>
          <div class="panel-heading">
            <div>
              <span class="eyebrow">COMPOSIÇÃO</span>
              <h2>Distribuição dos registros</h2>
            </div>
            <Layers3 :size="18" class="muted" />
          </div>
          <label v-if="categories.length" class="chart-field"
            >Categoria<select v-model="categoryField">
              <option v-for="column in categories" :key="column.name" :value="column.name">
                {{ column.name }}
              </option>
            </select></label
          ><DistributionChart :groups="distribution?.groups || []" />
          <p class="chart-footnote">
            Contagem por categoria{{
              dateField
                ? ' no período selecionado'
                : ' · dataset sem coluna de data, período não aplicável'
            }}.
          </p>
        </section>
      </div>
      <section class="panel" data-reveal>
        <div class="panel-heading">
          <div>
            <span class="eyebrow">O QUE MOVE SEU NEGÓCIO</span>
            <h2>Indicadores de desempenho</h2>
          </div>
          <RouterLink to="/kpis" class="inline-link"
            >Todos os KPIs <ArrowUpRight :size="14"
          /></RouterLink>
        </div>
        <div v-if="summary.kpis.length" class="kpi-grid">
          <article v-for="kpi in summary.kpis" :key="kpi.id" class="kpi-tile">
            <div>
              <span class="kpi-dot" /><span>{{ kpi.name }}</span
              ><Gauge :size="16" />
            </div>
            <strong>{{ format(kpi.value) }}</strong
            ><template v-if="progress(kpi) !== null"
              ><div
                class="progress-track"
                role="progressbar"
                :aria-label="`Meta de ${kpi.name}`"
                :aria-valuenow="progress(kpi)"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                <span :style="{ width: `${progress(kpi)}%` }" />
              </div>
              <p>{{ format(progress(kpi)) }}% da meta de {{ format(kpi.target) }}</p></template
            >
            <p v-else>Meta: {{ format(kpi.target) }}</p>
          </article>
        </div>
        <EmptyState
          v-else
          title="Defina o que importa para o seu negócio"
          description="Crie seu primeiro KPI para acompanhar resultados e metas."
          ><RouterLink to="/kpis" class="button secondary small"
            >Criar indicador <ArrowRight :size="14" /></RouterLink
        ></EmptyState>
      </section>
      <div class="two-col">
        <section class="panel insight-panel" data-reveal>
          <div class="panel-heading">
            <div>
              <span class="eyebrow">SINAIS NOS SEUS DADOS</span>
              <h2><Sparkles :size="18" /> Insights relevantes</h2>
            </div>
            <RouterLink to="/insights" class="inline-link"
              >Explorar <ArrowUpRight :size="14"
            /></RouterLink>
          </div>
          <article v-for="insight in summary.insights" :key="insight.id" class="feed-item">
            <span class="feed-icon"><Sparkles :size="17" /></span>
            <div>
              <span class="badge">ANÁLISE ESTATÍSTICA</span>
              <h3>{{ insight.title }}</h3>
              <p>
                {{ insight.details.anomaly_count }} valores atípicos em
                {{ insight.details.sample_size }} registros. Regra |z-score| &gt; 3.
              </p>
            </div>
          </article>
          <EmptyState
            v-if="!summary.insights.length"
            title="Nenhuma anomalia identificada"
            description="Novos insights aparecem quando os dados atendem às regras estatísticas. Não utilizamos previsões de IA."
          />
        </section>
        <section class="panel" data-reveal>
          <div class="panel-heading">
            <div>
              <span class="eyebrow">MONITORAMENTO</span>
              <h2><Bell :size="18" /> Alertas recentes</h2>
            </div>
            <RouterLink to="/alerts" class="inline-link"
              >Ver todos <ArrowUpRight :size="14"
            /></RouterLink>
          </div>
          <article v-for="alert in summary.recent_alerts" :key="alert.id" class="feed-item">
            <span class="feed-icon" :class="{ warning: alert.enabled && alert.triggered }"
              ><Bell :size="17"
            /></span>
            <div>
              <h3>{{ alert.name }}</h3>
              <p>Valor {{ format(alert.last_value) }} · limite {{ format(alert.threshold) }}</p>
              <span class="badge" :class="{ warning: alert.enabled && alert.triggered }">{{
                !alert.enabled
                  ? 'Desativado'
                  : alert.triggered
                    ? 'Limite atingido'
                    : 'Dentro do limite'
              }}</span>
            </div>
          </article>
          <EmptyState
            v-if="!summary.recent_alerts.length"
            title="Seus indicadores, sob controle"
            description="Configure limites personalizados e acompanhe os alertas por aqui."
          />
        </section>
      </div>
    </div>
    <section
      v-show="activeTab === 'activity'"
      id="activity-panel"
      role="tabpanel"
      aria-labelledby="activity-tab"
      class="panel"
    >
      <div class="panel-heading">
        <h2><Clock3 :size="18" /> Atividade recente</h2>
        <span class="badge">ÚLTIMAS 5 IMPORTAÇÕES</span>
      </div>
      <article v-for="job in jobs" :key="job.id" class="activity-item">
        <span class="feed-icon"><UploadCloud :size="18" /></span>
        <div>
          <strong>{{ job.filename }}</strong>
          <p>
            {{ job.imported_rows }} importados · {{ job.duplicate_rows }} duplicados ·
            {{ job.rejected_rows }} rejeitados
          </p>
        </div>
        <span class="badge" :class="{ warning: job.status !== 'completed' }">{{ job.status }}</span
        ><time>{{ date(job.created_at) }}</time>
      </article>
      <EmptyState
        v-if="!jobs.length"
        title="Sua jornada de dados começa agora"
        description="O histórico das suas importações aparecerá aqui."
      />
    </section>
    <section class="panel processing-panel" data-reveal>
      <div class="panel-heading">
        <div>
          <span class="eyebrow">PIPELINE DE DADOS</span>
          <h2>Histórico de processamento</h2>
        </div>
        <RouterLink to="/ingestion" class="inline-link"
          >Ver histórico <ArrowUpRight :size="14"
        /></RouterLink>
      </div>
      <DataTable
        :rows="jobs"
        :columns="[
          { key: 'filename', label: 'Arquivo / origem' },
          { key: 'status', label: 'Status' },
          { key: 'imported_rows', label: 'Importados' },
          { key: 'duplicate_rows', label: 'Duplicados' },
          { key: 'created_at', label: 'Processado em', render: (row) => date(row.created_at) },
        ]"
        caption="Histórico de processamento"
      />
    </section>
    <div class="dashboard-bottom-note">
      <span class="status-dot" /> Analytics com dados reais. Sem adivinhação.<span
        >DataPulse Intelligence Platform</span
      >
    </div>
  </div>
</template>
