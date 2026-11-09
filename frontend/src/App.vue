<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { useRouter } from 'vue-router'
import {
  Activity,
  ArrowRight,
  ShieldCheck,
  Database,
  ChartNoAxesCombined,
  Sparkles,
  Sun,
  Moon,
  BookOpen,
} from '@lucide/vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/services/api'
import { useInterfaceStore } from '@/stores/interface'
import { pageEnter } from '@/composables/motion'
import AppSidebar from '@/components/AppSidebar.vue'
import AppHeader from '@/components/AppHeader.vue'
import Backgorund from '@/components/backgorund.vue'
import Notification from '@/components/ui/Notification.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import AppDialog from '@/components/ui/AppDialog.vue'
import ProductTour from '@/components/ProductTour.vue'

const auth = useAuthStore()
const ui = useInterfaceStore()
const router = useRouter()
const shell = ref(null)
let sidebarContext
let sidebarMedia
let priorFocus
const mode = ref('login')
const credentials = ref({ name: '', username: '', email: '', password: '' })
const error = ref('')
const busy = ref(false)
const restoring = ref(true)
const menuOpen = ref(false)
const mobileQuery = globalThis.matchMedia('(max-width: 900px)')
const isMobile = ref(mobileQuery.matches)
function viewportChanged(event) {
  isMobile.value = event.matches
  if (!event.matches) menuOpen.value = false
}
const registrationOpen = ref(false)
const guideOpen = ref(false)
const guideBusy = ref(false)
const guideError = ref('')
const demoAccess = ref(null)
const copiedField = ref('')
const tourOpen = ref(false)
const tourInvite = ref(false)
let copyResetTimeout
watch([() => ui.collapsed, () => auth.user], async () => {
  await nextTick()
  sidebarMedia?.revert()
  sidebarContext?.revert()
  if (!shell.value) return
  sidebarContext = gsap.context(() => {
    sidebarMedia = gsap.matchMedia()
    sidebarMedia.add('(min-width: 901px) and (prefers-reduced-motion: no-preference)', () => {
      gsap.fromTo(
        shell.value,
        { '--sidebar-width': ui.collapsed ? '244px' : '76px' },
        {
          '--sidebar-width': ui.collapsed ? '76px' : '244px',
          duration: 0.24,
          ease: 'power2.out',
          clearProps: '--sidebar-width',
        },
      )
    })
  }, shell.value)
})
watch(menuOpen, async (open) => {
  if (open) priorFocus = document.activeElement
  document.body.style.overflow = open ? 'hidden' : ''
  await nextTick()
  if (open) document.querySelector('#main-sidebar a')?.focus()
  else priorFocus?.focus()
})
function menuKeys(event) {
  if (!menuOpen.value) return
  if (event.key === 'Escape') {
    menuOpen.value = false
    return
  }
  if (event.key !== 'Tab') return
  const items = [...document.querySelectorAll('#main-sidebar a, #main-sidebar button')].filter(
    (el) => el.getClientRects().length,
  )
  const first = items[0],
    last = items.at(-1)
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await auth.authenticate(
      mode.value,
      mode.value === 'register'
        ? { ...credentials.value, email: credentials.value.email || null }
        : { username: credentials.value.username, password: credentials.value.password },
    )
    const tourKey = `datapulse-tour-${auth.user.id}`
    if (!localStorage.getItem(tourKey)) {
      tourInvite.value = true
      tourOpen.value = true
    }
    registrationOpen.value = false
    mode.value = 'login'
    credentials.value.password = ''
  } catch (exc) {
    error.value = [
      exc.message,
      ...(Array.isArray(exc.details) ? exc.details.map((d) => d.message) : []),
    ].join(': ')
  } finally {
    busy.value = false
  }
}

function startTour() {
  tourInvite.value = false
  tourOpen.value = true
  router.push('/dashboard')
}
function closeTour(status) {
  localStorage.setItem(`datapulse-tour-${auth.user.id}`, status)
  tourOpen.value = false
}
function beginTour() {
  tourInvite.value = false
  router.push('/dashboard')
}
function expired() {
  auth.logout()
  error.value = 'Sessao expirada ou acesso revogado. Entre novamente.'
}
function toggleAuthMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}
async function showDemoGuide() {
  guideOpen.value = true
  guideError.value = ''
  copiedField.value = ''
  if (demoAccess.value?.available) return
  guideBusy.value = true
  try {
    demoAccess.value = (await api('/auth/demo')).data
  } catch (exc) {
    guideError.value = exc.message
  } finally {
    guideBusy.value = false
  }
}
async function copyDemoCredential(field, label) {
  guideError.value = ''
  try {
    await navigator.clipboard.writeText(demoAccess.value[field])
    copiedField.value = field
    window.clearTimeout(copyResetTimeout)
    copyResetTimeout = window.setTimeout(() => {
      copiedField.value = ''
    }, 1800)
  } catch {
    guideError.value = `Não foi possível copiar ${label}. Selecione e copie o valor manualmente.`
  }
}
function useDemoCredentials() {
  credentials.value.username = demoAccess.value.username
  credentials.value.password = demoAccess.value.password
  mode.value = 'login'
  error.value = ''
  guideOpen.value = false
}
onMounted(async () => {
  mobileQuery.addEventListener('change', viewportChanged)
  globalThis.addEventListener('datapulse:unauthorized', expired)
  globalThis.addEventListener('keydown', menuKeys)
  try {
    await auth.restore()
    registrationOpen.value = (await api('/auth/setup')).data.registration_open
  } catch (exc) {
    auth.logout()
    error.value = exc.message
  } finally {
    restoring.value = false
  }
})
onUnmounted(() => {
  mobileQuery.removeEventListener('change', viewportChanged)
  globalThis.removeEventListener('datapulse:unauthorized', expired)
  globalThis.removeEventListener('keydown', menuKeys)
  document.body.style.overflow = ''
  window.clearTimeout(copyResetTimeout)
  sidebarMedia?.revert()
  sidebarContext?.revert()
})
</script>

<template>
  <Backgorund />
  <div v-if="restoring" class="auth-screen"><LoadingState /></div>
  <div v-else-if="!auth.user" class="auth-screen">
    <section class="auth-story">
      <div class="brand">
        <span class="brand-icon"><Activity :size="23" /></span>DataPulse<span class="brand-dot"
          >.</span
        >
      </div>
      <p class="eyebrow">DATA INTELLIGENCE PLATFORM</p>
      <h1>
        Dados conectados.<br /><span>Decisões que<br />movem o futuro.</span>
      </h1>
      <p>
        Transforme informacoes em indicadores, tendencias e decisoes com uma plataforma integrada de
        analytics.
      </p>
      <div class="auth-features">
        <span><Database :size="18" /> Conecte suas fontes</span
        ><span><ChartNoAxesCombined :size="18" /> Explore seus indicadores</span
        ><span><Sparkles :size="18" /> Descubra novas perspectivas</span>
      </div>
      <p class="small">
        <ShieldCheck :size="15" /> Dados sintéticos para demonstração. Acesso por permissões.
      </p>
    </section>
    <section class="auth-card">
      <div class="auth-card-top">
        <span class="badge">SEU WORKSPACE DE INTELIGÊNCIA</span>
        <div class="auth-card-actions">
          <button
            v-if="mode === 'login'"
            class="auth-guide-button"
            type="button"
            aria-haspopup="dialog"
            @click="showDemoGuide"
          >
            <BookOpen :size="15" /> GUIA
          </button>
          <button
          class="icon-button"
          type="button"
          :aria-label="ui.theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'"
          @click="ui.toggleTheme"
          >
            <component :is="ui.theme === 'dark' ? Sun : Moon" :size="18" />
          </button>
        </div>
      </div>
      <h2>{{ mode === 'login' ? 'Acesse seu workspace' : 'Crie sua conta' }}</h2>
      <p class="muted">
        {{
          mode === 'login'
            ? 'Entre para continuar sua analise. Solicite sua conta ao administrador da equipe.'
            : 'Cadastro inicial do administrador. Os proximos membros serao adicionados nas configuracoes da equipe.'
        }}
      </p>
      <Notification v-if="error" :message="error" kind="error" @dismiss="error = ''" />
      <form @submit.prevent="submit">
        <label v-if="mode === 'register'"
          >Nome<input
            v-model="credentials.name"
            autocomplete="name"
            required
            minlength="2"
            maxlength="100" /></label
        ><label
          >Usuário<input
            v-model="credentials.username"
            autocomplete="username"
            required
            minlength="3"
            maxlength="32"
            pattern="[A-Za-z0-9._-]+" /></label
        ><label v-if="mode === 'register'"
          >Email de contato (opcional)<input
            v-model="credentials.email"
            type="email"
            autocomplete="email"
            maxlength="254" /></label
        ><label
          >Senha<input
            v-model="credentials.password"
            type="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            :minlength="mode === 'register' ? 10 : 1"
            maxlength="128"
            required /></label
        ><button class="button" :disabled="busy">
          {{
            busy
              ? 'Aguarde...'
              : mode === 'login'
                ? 'Entrar no workspace'
                : 'Cadastrar administrador'
          }}
          <ArrowRight :size="17" />
        </button>
      </form>
      <button
        v-if="registrationOpen"
        class="text-button auth-switch"
        :disabled="busy"
        @click="toggleAuthMode"
      >
        {{
          mode === 'login' ? 'Primeiro acesso? Configurar administrador' : 'Ja tenho conta. Entrar'
        }}
      </button>
    </section>
    <AppDialog
      class="demo-guide-dialog"
      :open="guideOpen"
      title="Acesso de demonstração"
      @close="guideOpen = false"
    >
      <div class="demo-guide-intro">
        <span class="demo-guide-icon"><BookOpen :size="19" /></span>
        <div>
          <span class="demo-guide-kicker">CONTA PÚBLICA · PERMISSÃO EDITOR</span>
          <p>
            Use a conta pública para explorar o workspace. As alterações ficam visíveis para todos
            que compartilham este banco.
          </p>
        </div>
      </div>
      <p v-if="guideBusy" class="demo-guide-status" role="status">Carregando acesso...</p>
      <Notification
        v-if="guideError"
        :message="guideError"
        kind="error"
        @dismiss="guideError = ''"
      />
      <div v-if="demoAccess?.available" class="demo-guide-content">
        <dl class="demo-credentials">
          <div class="demo-credential">
            <dt>Usuário</dt>
            <dd><code>{{ demoAccess.username }}</code></dd>
            <button
              class="demo-copy-button"
              type="button"
              :aria-label="copiedField === 'username' ? 'Usuário copiado' : 'Copiar usuário'"
              @click="copyDemoCredential('username', 'o usuário')"
            >
              {{ copiedField === 'username' ? 'Copiado' : 'Copiar' }}
            </button>
          </div>
          <div class="demo-credential">
            <dt>Senha</dt>
            <dd><code>{{ demoAccess.password }}</code></dd>
            <button
              class="demo-copy-button"
              type="button"
              :aria-label="copiedField === 'password' ? 'Senha copiada' : 'Copiar senha'"
              @click="copyDemoCredential('password', 'a senha')"
            >
              {{ copiedField === 'password' ? 'Copiado' : 'Copiar' }}
            </button>
          </div>
          <div class="demo-role">
            <dt>O que você pode fazer</dt>
            <dd>Criar e explorar fontes, datasets e indicadores.</dd>
          </div>
        </dl>
        <p v-if="copiedField" class="demo-copy-status" role="status">Credencial copiada.</p>
        <div class="demo-guide-warning">
          <ShieldCheck :size="16" />
          <p>Esta conta é compartilhada. Não use dados reais ou confidenciais.</p>
        </div>
        <button class="button" type="button" @click="useDemoCredentials">
          Preencher acesso demo <ArrowRight :size="17" />
        </button>
      </div>
      <p v-else-if="demoAccess && !guideBusy" class="muted demo-guide-status" role="status">
        A conta pública ainda não está disponível. Peça a um administrador para habilitar o modo demo
        ou criar/reativar a conta em Configurações.
      </p>
      <button
        v-if="guideError"
        class="text-button demo-guide-retry"
        type="button"
        :disabled="guideBusy"
        @click="showDemoGuide"
      >
        Tentar novamente
      </button>
    </AppDialog>
  </div>
  <div
    v-else
    ref="shell"
    class="app-shell"
    :class="{ 'sidebar-is-collapsed': ui.collapsed }"
    :inert="tourOpen && !tourInvite || undefined"
  >
    <a class="skip-link" href="#main-content">Pular para o conteúdo</a>
    <AppSidebar :open="menuOpen" :mobile="isMobile" @close="menuOpen = false" />
    <button
      v-if="menuOpen"
      class="menu-overlay"
      aria-label="Fechar menu de navegação"
      tabindex="-1"
      @click="menuOpen = false"
    />
    <div class="workspace" :inert="menuOpen || undefined">
      <AppHeader
        :menu-open="menuOpen"
        @menu="menuOpen = !menuOpen"
        @start-tour="startTour"
      />
      <main id="main-content" tabindex="-1">
        <RouterView v-slot="{ Component, route }"
          ><Transition :css="false" @enter="pageEnter"
            ><component :is="Component" :key="route.meta.section" /></Transition
        ></RouterView>
      </main>
      <footer class="main-footer">
        <span><Activity :size="13" /> DataPulse Intelligence Platform</span
        ><span>Construído para decisões melhores.</span>
      </footer>
    </div>
    <ProductTour
      :open="tourOpen"
      :invite="tourInvite"
      @close="closeTour('skipped')"
      @begin="beginTour"
      @complete="closeTour('completed')"
    />
  </div>
</template>
