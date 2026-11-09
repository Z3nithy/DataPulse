<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, BookOpen, Check, Compass } from '@lucide/vue'
import AppDialog from '@/components/ui/AppDialog.vue'

const props = defineProps({
  open: Boolean,
  invite: Boolean,
})
const emit = defineEmits(['close', 'begin', 'complete'])
const router = useRouter()
const stepIndex = ref(0)
const spotlightStyle = ref(null)
const tooltipStyle = ref(null)
const tooltip = ref(null)
const nextButton = ref(null)
const viewport = ref({ width: 0, height: 0 })
let currentTarget = null
let targetObserver
let repositionFrame = 0

const steps = [
  {
    section: 'Visão geral',
    title: 'Leia o resumo do workspace',
    description:
      'Os cartões mostram registros, fontes, datasets, KPIs, insights e alertas. Clique em um cartão para abrir a área correspondente.',
    to: '/dashboard',
    target: 'dashboard',
  },
  {
    section: 'Fontes de dados',
    title: 'Conecte a origem dos dados',
    description:
      'Cadastre de onde os dados vêm: arquivos, planilhas, JSON ou uma API autorizada. A fonte pode ser vinculada a um dataset.',
    to: '/sources',
    target: 'sources',
  },
  {
    section: 'Datasets',
    title: 'Organize os dados para análise',
    description:
      'Um dataset reúne os registros e define a estrutura das colunas. Você pode vinculá-lo a uma fonte ou enviar um arquivo diretamente.',
    to: '/datasets',
    target: 'datasets',
  },
  {
    section: 'Importações',
    title: 'Carregue e valide arquivos',
    description:
      'Escolha o dataset e envie CSV, Excel ou JSON. O DataPulse valida os registros e acompanha o histórico e os resultados do processamento.',
    to: '/ingestion',
    target: 'ingestion',
  },
  {
    section: 'Analytics',
    title: 'Faça perguntas aos dados',
    description:
      'Escolha um dataset, uma métrica e filtros para executar análises sem precisar escrever SQL. Os resultados podem ser agrupados e comparados.',
    to: '/analytics',
    target: 'analytics',
  },
  {
    section: 'Tendências',
    title: 'Compare períodos',
    description:
      'Use a consulta temporal para acompanhar a evolução dos resultados e comparar o período atual com o anterior.',
    to: '/trends',
    target: 'trends',
  },
  {
    section: 'KPIs',
    title: 'Acompanhe metas importantes',
    description:
      'Defina um indicador a partir de uma consulta e, se quiser, informe uma meta para acompanhar o desempenho ao longo do tempo.',
    to: '/kpis',
    target: 'kpis',
  },
  {
    section: 'Alertas',
    title: 'Receba avisos sobre limites',
    description:
      'Crie regras para um KPI e escolha a condição e o limite. Os alertas ajudam a identificar quando um valor precisa de atenção.',
    to: '/alerts',
    target: 'alerts',
  },
  {
    section: 'Insights',
    title: 'Investigue sinais estatísticos',
    description:
      'Consulte possíveis anomalias calculadas a partir dos dados. Os insights usam regras estatísticas e não são previsões de IA.',
    to: '/insights',
    target: 'insights',
  },
  {
    section: 'Relatórios',
    title: 'Registre e exporte resultados',
    description:
      'Salve uma análise como relatório e exporte os resultados em CSV para compartilhar ou continuar trabalhando neles.',
    to: '/reports',
    target: 'reports',
  },
  {
    section: 'Configurações',
    title: 'Confira o workspace e as permissões',
    description:
      'Veja sua conta e papel no workspace. Administradores também podem gerenciar membros, permissões e configurações da equipe.',
    to: '/settings',
    target: 'settings',
  },
]
const step = computed(() => steps[stepIndex.value])
const isLastStep = computed(() => stepIndex.value === steps.length - 1)
const dimPath = computed(() => {
  const { width, height } = viewport.value
  const box = spotlightStyle.value
  if (!width || !height || !box) return ''
  const left = Number.parseFloat(box.left)
  const top = Number.parseFloat(box.top)
  const right = left + Number.parseFloat(box.width)
  const bottom = top + Number.parseFloat(box.height)
  return `M0 0H${width}V${height}H0Z M${left} ${top}H${right}V${bottom}H${left}Z`
})

watch(
  () => [props.open, props.invite],
  ([open, invite]) => {
    if (open && !invite) {
      stepIndex.value = 0
      showStep()
    } else {
      clearSpotlight()
    }
  },
)

function clearSpotlight() {
  currentTarget = null
  targetObserver?.disconnect()
  spotlightStyle.value = null
  tooltipStyle.value = null
}

function waitFrame() {
  return new Promise((resolve) => requestAnimationFrame(resolve))
}

async function showStep() {
  clearSpotlight()
  await router.push(step.value.to)
  await nextTick()

  let target
  for (let attempt = 0; attempt < 90; attempt++) {
    target = document.querySelector(`[data-tour="${step.value.target}"]`)
    if (target) break
    await waitFrame()
  }
  target ||= document.querySelector('.page-heading')
  if (!target || !props.open || props.invite) return

  currentTarget = target
  target.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    block: 'center',
    inline: 'nearest',
  })
  await waitFrame()
  await waitFrame()
  updatePosition()
  targetObserver = new ResizeObserver(schedulePosition)
  targetObserver.observe(target)
  await nextTick()
  updatePosition()
  nextButton.value?.focus({ preventScroll: true })
}

function updatePosition() {
  if (!currentTarget?.isConnected) return
  viewport.value = { width: window.innerWidth, height: window.innerHeight }
  const rect = currentTarget.getBoundingClientRect()
  const padding = 8
  const left = Math.max(8, rect.left - padding)
  const top = Math.max(8, rect.top - padding)
  const width = Math.min(window.innerWidth - 16, rect.width + padding * 2)
  const height = Math.min(window.innerHeight - 16, rect.height + padding * 2)
  spotlightStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
  }
  placeTooltip(rect)
}

function placeTooltip(targetRect) {
  if (!tooltip.value) return
  const gap = 18
  const margin = 12
  const tooltipRect = tooltip.value.getBoundingClientRect()
  const tooltipWidth = tooltipRect.width
  const tooltipHeight = tooltipRect.height
  const left = Math.min(
    Math.max(margin, targetRect.left + targetRect.width / 2 - tooltipWidth / 2),
    window.innerWidth - tooltipWidth - margin,
  )
  const below = targetRect.bottom + gap
  const top =
    below + tooltipHeight <= window.innerHeight - margin
      ? below
      : targetRect.top - tooltipHeight - gap >= margin
        ? targetRect.top - tooltipHeight - gap
        : Math.max(margin, (window.innerHeight - tooltipHeight) / 2)
  tooltipStyle.value = { left: `${left}px`, top: `${top}px` }
}

function schedulePosition() {
  if (repositionFrame) cancelAnimationFrame(repositionFrame)
  repositionFrame = requestAnimationFrame(() => {
    repositionFrame = 0
    updatePosition()
  })
}

async function moveStep(direction) {
  const nextIndex = stepIndex.value + direction
  if (nextIndex < 0 || nextIndex >= steps.length) return
  stepIndex.value = nextIndex
  await showStep()
}

function nextStep() {
  if (isLastStep.value) {
    emit('complete')
    return
  }
  moveStep(1)
}

function beginTour() {
  stepIndex.value = 0
  emit('begin')
}

watch(
  () => props.open && !props.invite,
  (active) => {
    if (active) {
      window.addEventListener('resize', schedulePosition)
      window.addEventListener('scroll', schedulePosition, true)
    } else {
      window.removeEventListener('resize', schedulePosition)
      window.removeEventListener('scroll', schedulePosition, true)
      clearSpotlight()
    }
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', schedulePosition)
  window.removeEventListener('scroll', schedulePosition, true)
  targetObserver?.disconnect()
  if (repositionFrame) cancelAnimationFrame(repositionFrame)
})
</script>

<template>
  <AppDialog
    :open="open && invite"
    title="Conheça o DataPulse"
    @close="emit('close')"
  >
    <section class="product-tour-invite">
      <span class="product-tour-icon"><Compass :size="22" /></span>
      <p class="muted">
        O tour é opcional e percorre as principais áreas do workspace. Cada etapa destaca uma
        ferramenta e explica para que serve; você pode sair quando quiser.
      </p>
      <div class="product-tour-actions">
        <button class="button secondary" type="button" @click="emit('close')">Agora não</button>
        <button class="button" type="button" @click="beginTour">
          Começar tour <ArrowRight :size="16" />
        </button>
      </div>
    </section>
  </AppDialog>

  <Teleport to="body">
    <template v-if="open && !invite && spotlightStyle">
      <svg
        class="product-tour-dimmer"
        :viewBox="`0 0 ${viewport.width} ${viewport.height}`"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path :d="dimPath" fill="#030712c9" fill-rule="evenodd" />
      </svg>
      <div class="product-tour-spotlight" :style="spotlightStyle" aria-hidden="true" />
      <section
        ref="tooltip"
        class="product-tour-tooltip"
        :style="tooltipStyle"
        role="dialog"
        aria-modal="true"
        :aria-label="`Etapa ${stepIndex + 1}: ${step.title}`"
        aria-live="polite"
      >
        <div class="product-tour-progress">
          <span class="product-tour-icon"><BookOpen :size="19" /></span>
          <span>ETAPA {{ stepIndex + 1 }} DE {{ steps.length }}</span>
        </div>
        <div class="product-tour-progress-bar" aria-hidden="true">
          <span :style="{ width: `${((stepIndex + 1) / steps.length) * 100}%` }" />
        </div>
        <p class="product-tour-section">{{ step.section }}</p>
        <h2>{{ step.title }}</h2>
        <p class="muted product-tour-description">{{ step.description }}</p>
        <div class="product-tour-actions">
          <button
            v-if="stepIndex > 0"
            class="button secondary"
            type="button"
            @click="moveStep(-1)"
          >
            <ArrowLeft :size="15" /> Voltar
          </button>
          <button
            v-else
            class="button secondary product-tour-exit"
            type="button"
            @click="emit('close')"
          >
            Sair do tour
          </button>
          <button
            v-if="stepIndex > 0"
            class="text-button product-tour-exit"
            type="button"
            @click="emit('close')"
          >
            Sair
          </button>
          <button
            ref="nextButton"
            class="button"
            type="button"
            @click="nextStep"
          >
            <template v-if="isLastStep">Concluir <Check :size="16" /></template>
            <template v-else>Próximo <ArrowRight :size="16" /></template>
          </button>
        </div>
      </section>
    </template>
  </Teleport>
</template>
