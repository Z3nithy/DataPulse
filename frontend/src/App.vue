<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import {
  Activity,
  ArrowRight,
  ShieldCheck,
  Database,
  ChartNoAxesCombined,
  Sparkles,
  Sun,
  Moon,
} from '@lucide/vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/services/api'
import { useInterfaceStore } from '@/stores/interface'
import { pageEnter } from '@/composables/motion'
import AppSidebar from '@/components/AppSidebar.vue'
import AppHeader from '@/components/AppHeader.vue'
import Notification from '@/components/ui/Notification.vue'
import LoadingState from '@/components/ui/LoadingState.vue'

const auth = useAuthStore()
const ui = useInterfaceStore()
const shell = ref(null)
let sidebarContext
let sidebarMedia
let priorFocus
const mode = ref('login')
const credentials = ref({ name: '', email: '', password: '' })
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
        ? credentials.value
        : { email: credentials.value.email, password: credentials.value.password },
    )
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

function expired() {
  auth.logout()
  error.value = 'Sessao expirada ou acesso revogado. Entre novamente.'
}
function toggleAuthMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
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
  sidebarMedia?.revert()
  sidebarContext?.revert()
})
</script>

<template>
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
        <ShieldCheck :size="15" /> Análises reais. Acesso seguro. Sem dados simulados.
      </p>
    </section>
    <section class="auth-card">
      <div class="auth-card-top">
        <span class="badge">SEU WORKSPACE DE INTELIGÊNCIA</span
        ><button
          class="icon-button"
          :aria-label="ui.theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'"
          @click="ui.toggleTheme"
        >
          <component :is="ui.theme === 'dark' ? Sun : Moon" :size="18" />
        </button>
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
          >Email<input
            v-model="credentials.email"
            type="email"
            autocomplete="username"
            required
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
  </div>
  <div v-else ref="shell" class="app-shell" :class="{ 'sidebar-is-collapsed': ui.collapsed }">
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
      <AppHeader :menu-open="menuOpen" @menu="menuOpen = !menuOpen" />
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
  </div>
</template>
