<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { useRoute } from 'vue-router'
import {
  Bell,
  ChevronRight,
  ChevronDown,
  Search,
  Sun,
  Moon,
  Menu,
  LogOut,
  Settings,
  ExternalLink,
  BookOpen,
  CircleAlert,
  CheckCheck,
  X,
} from '@lucide/vue'
import { useAuthStore } from '@/stores/auth'
import { useInterfaceStore } from '@/stores/interface'
import { navigation } from '@/services/navigation'
import { api, docsUrl, post } from '@/services/api'
import { useReveal } from '@/composables/motion'
import DateRangePicker from './ui/DateRangePicker.vue'
import GlobalSearch from './GlobalSearch.vue'
import LoadingState from './ui/LoadingState.vue'
import Notification from './ui/Notification.vue'
const emit = defineEmits(['menu', 'start-tour'])
const props = defineProps({ menuOpen: Boolean })
const route = useRoute()
const auth = useAuthStore()
const ui = useInterfaceStore()
const searchOpen = ref(false)
const notificationsOpen = ref(false)
const notifications = ref(null)
const notificationsTrigger = ref(null)
let notificationsRequest = 0
useReveal(notifications, () => notificationsOpen.value)
const events = ref([])
const unread = ref(0)
const notificationPage = ref(1)
const notificationTotal = ref(0)
const updating = ref(false)
let polling
let disposed = false
const busy = ref(false)
const signingOut = ref(false)
const error = ref('')
const profile = ref(null)
const profileOpen = ref(false)
useReveal(profile, () => profileOpen.value)
const current = computed(
  () => navigation.find((item) => item.path === route.meta.section)?.label || 'Workspace',
)
function startTour() {
  profile.value.open = false
  emit('start-tour')
}
async function showNotifications() {
  if (notificationsOpen.value) {
    closeNotifications()
    return
  }
  if (profile.value) profile.value.open = false
  notificationsOpen.value = true
  await loadNotifications(1)
}
async function loadNotifications(page = notificationPage.value) {
  const request = ++notificationsRequest
  busy.value = true
  error.value = ''
  try {
    const response = await api(`/notifications?page=${page}&page_size=20`)
    if (request === notificationsRequest && !disposed) {
      events.value = response.data
      unread.value = response.meta.unread
      notificationPage.value = page
      notificationTotal.value = response.meta.total
    }
  } catch (exc) {
    if (request === notificationsRequest) error.value = exc.message
  } finally {
    if (request === notificationsRequest) busy.value = false
  }
}
async function markRead(item) {
  updating.value = true
  error.value = ''
  try {
    if (item) await api(`/notifications/${item.id}/read`, { method: 'PATCH' })
    else await post('/notifications/read-all', {})
    await loadNotifications()
  } catch (exc) {
    error.value = exc.message
  } finally {
    updating.value = false
  }
}
async function signOut() {
  signingOut.value = true
  error.value = ''
  const workspace = document.querySelector('.app-shell')
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches
  try {
    const request = post('/auth/logout', {})
    if (workspace && !reduceMotion) {
      const exit = gsap.to(workspace, {
        autoAlpha: 0,
        scale: 0.985,
        filter: 'blur(8px)',
        transformOrigin: '50% 50%',
        duration: 0.38,
        ease: 'power2.in',
      })
      await Promise.all([request, exit.then()])
    } else {
      await request
    }
    auth.logout()
    if (!reduceMotion) {
      await nextTick()
      gsap.fromTo(
        '.auth-story, .auth-card',
        { autoAlpha: 0, y: 18, filter: 'blur(6px)' },
        {
          autoAlpha: 1,
          y: 0,
          filter: 'blur(0px)',
          duration: 0.42,
          stagger: 0.08,
          ease: 'power2.out',
          clearProps: 'filter,transform,opacity,visibility',
        },
      )
    }
  } catch (exc) {
    if (workspace?.isConnected && !reduceMotion) {
      gsap.killTweensOf(workspace)
      await gsap.to(workspace, {
        autoAlpha: 1,
        scale: 1,
        filter: 'blur(0px)',
        duration: 0.25,
        ease: 'power2.out',
        clearProps: 'filter,transform,opacity,visibility',
      })
    }
    error.value = exc.message
  } finally {
    signingOut.value = false
  }
}
async function pollNotifications() {
  if (!document.hidden && !busy.value && !updating.value) await loadNotifications()
  if (!disposed) polling = setTimeout(pollNotifications, 30000)
}
function closeNotifications(restoreFocus = false) {
  notificationsOpen.value = false
  busy.value = false
  notificationsRequest++
  if (restoreFocus) notificationsTrigger.value?.focus()
}
function notificationsFocusOut(event) {
  if (event.relatedTarget && !notifications.value?.contains(event.relatedTarget))
    closeNotifications()
}
watch(
  () => route.fullPath,
  () => closeNotifications(),
)
function keyboard(event) {
  if (!props.menuOpen && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    searchOpen.value = !searchOpen.value
  }
  if (event.key === 'Escape') {
    if (notificationsOpen.value) closeNotifications(true)
    if (profile.value) profile.value.open = false
  }
}
function outside(event) {
  if (profile.value && !profile.value.contains(event.target)) profile.value.open = false
  if (notifications.value && !notifications.value.contains(event.target)) closeNotifications()
}
onMounted(() => {
  pollNotifications()
  globalThis.addEventListener('keydown', keyboard)
  globalThis.addEventListener('click', outside)
})
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(polling)
  notificationsRequest++
  globalThis.removeEventListener('keydown', keyboard)
  globalThis.removeEventListener('click', outside)
})
</script>
<template>
  <header class="topbar">
    <div class="header-left">
      <button
        class="icon-button mobile-only"
        aria-label="Abrir ou fechar menu"
        aria-controls="main-sidebar"
        :aria-expanded="menuOpen"
        @click="$emit('menu')"
      >
        <Menu :size="20" />
      </button>
      <nav class="breadcrumbs" aria-label="Breadcrumb">
        <RouterLink to="/dashboard">Workspace</RouterLink><ChevronRight :size="13" /><span
          aria-current="page"
          >{{ current }}</span
        >
      </nav>
    </div>
    <button class="header-search" aria-haspopup="dialog" @click="searchOpen = true">
      <Search :size="16" /><span>Buscar no workspace...</span><kbd>Ctrl K</kbd>
    </button>
    <div class="header-actions">
      <DateRangePicker /><button
        class="icon-button"
        :aria-label="ui.theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'"
        @click="ui.toggleTheme"
      >
        <component :is="ui.theme === 'dark' ? Sun : Moon" :size="18" />
      </button>
      <div ref="notifications" class="notifications-dropdown" @focusout="notificationsFocusOut">
        <button
          ref="notificationsTrigger"
          class="icon-button notifications-trigger"
          :aria-label="`Central de notificações${unread ? `: ${unread} não lidas` : ''}`"
          aria-controls="notifications-panel"
          :aria-expanded="notificationsOpen"
          @click="showNotifications"
        >
          <Bell :size="18" />
          <span v-if="unread" class="notification-count" aria-hidden="true">{{
            unread > 99 ? '99+' : unread
          }}</span>
        </button>
        <section
          v-if="notificationsOpen"
          id="notifications-panel"
          class="notifications-panel"
          aria-labelledby="notifications-title"
          data-reveal
        >
          <div class="notifications-heading">
            <h2 id="notifications-title">Notificações</h2>
            <button
              type="button"
              class="icon-button"
              aria-label="Fechar notificações"
              @click="closeNotifications(true)"
            >
              <X :size="16" />
            </button>
          </div>
          <p class="muted small notifications-description">
            Histórico de eventos · {{ unread }} não lidas.
          </p>
          <div class="notification-actions">
            <button
              type="button"
              class="text-button"
              :disabled="!unread || updating"
              @click="markRead()"
            >
              Marcar todas como lidas
            </button>
            <button type="button" class="text-button" :disabled="busy" @click="loadNotifications()">
              Atualizar
            </button>
          </div>
          <div class="notifications-list" :aria-busy="busy">
            <LoadingState v-if="busy" />
            <Notification v-if="error" kind="error" :message="error" @dismiss="error = ''" />
            <article
              v-for="item in events"
              :key="item.id"
              class="notification-item"
              :class="{ 'is-unread': !item.read_at }"
            >
              <component
                :is="!item.read_at ? CircleAlert : CheckCheck"
                :size="20"
                :class="!item.read_at ? 'text-warning' : 'text-success'"
              />
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.message }}</p>
                <small class="muted">{{ new Date(item.created_at).toLocaleString('pt-BR') }}</small>
                <div class="notification-actions">
                  <RouterLink :to="item.href" @click="closeNotifications()"
                    >Ver detalhes</RouterLink
                  >
                  <button
                    v-if="!item.read_at"
                    type="button"
                    class="text-button"
                    :disabled="updating"
                    @click="markRead(item)"
                  >
                    Marcar como lida
                  </button>
                </div>
              </div>
            </article>
            <div v-if="!busy && !events.length && !error" class="empty">
              <Bell :size="28" />
              <h3>Tudo tranquilo por aqui</h3>
              <p>Novas importações, relatórios e mudanças nos alertas aparecerão aqui.</p>
            </div>
            <div v-if="notificationTotal > 20" class="notification-actions">
              <button
                class="text-button"
                :disabled="busy || notificationPage === 1"
                @click="loadNotifications(notificationPage - 1)"
              >
                Mais recentes
              </button>
              <span class="muted small"
                >{{ notificationPage }} / {{ Math.ceil(notificationTotal / 20) }}</span
              >
              <button
                class="text-button"
                :disabled="busy || notificationPage * 20 >= notificationTotal"
                @click="loadNotifications(notificationPage + 1)"
              >
                Mais antigas
              </button>
            </div>
          </div>
          <RouterLink class="notifications-footer" to="/alerts" @click="closeNotifications()"
            >Gerenciar alertas <ChevronRight :size="14"
          /></RouterLink>
        </section>
      </div>
      <button
        class="icon-button mobile-search"
        aria-label="Busca global"
        @click="searchOpen = true"
      >
        <Search :size="18" />
      </button>
      <details ref="profile" class="profile-dropdown" @toggle="profileOpen = $event.target.open">
        <summary aria-label="Menu do perfil">
          <span class="avatar">{{ auth.user.name.slice(0, 2).toUpperCase() }}</span
          ><ChevronDown :size="13" />
        </summary>
        <div class="dropdown-menu" data-reveal>
          <strong>{{ auth.user.name }}</strong
          ><small>@{{ auth.user.username }}</small
          ><small v-if="auth.user.email">{{ auth.user.email }}</small
          ><span class="badge">{{
            { admin: 'Administrador', editor: 'Editor', viewer: 'Leitor' }[auth.user.role]
          }}</span>
          <hr />
          <Notification v-if="error" kind="error" :message="error" @dismiss="error = ''" />
          <RouterLink to="/settings" @click="profile.open = false"
            ><Settings :size="16" /> Configurações</RouterLink
          ><button @click="startTour"
            ><BookOpen :size="16" /> Fazer tour do sistema</button
          ><a :href="docsUrl" target="_blank" rel="noopener"
            ><ExternalLink :size="16" /> Documentação da API</a
          ><button :disabled="signingOut" @click="signOut"
            ><LogOut :size="16" />
            {{ signingOut ? 'Saindo...' : 'Sair de todas as sessões' }}</button
          >
        </div>
      </details>
    </div>
  </header>
  <GlobalSearch :open="searchOpen" @close="searchOpen = false" />
</template>
