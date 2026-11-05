<script setup>
import { Activity, PanelLeftClose, PanelLeftOpen, ArrowUpRight, Layers3, X } from '@lucide/vue'
import { navigation } from '@/services/navigation'
import { useInterfaceStore } from '@/stores/interface'
defineProps({ open: Boolean, mobile: Boolean })
defineEmits(['close'])
const ui = useInterfaceStore()
function positionTooltip(link) {
  const bounds = link.getBoundingClientRect()
  link.style.setProperty('--tooltip-top', `${bounds.top + bounds.height / 2}px`)
}
function scrollTooltip(event) {
  const link = event.currentTarget.querySelector('a:hover, a:focus-visible')
  if (link) positionTooltip(link)
}
</script>
<template>
  <aside
    id="main-sidebar"
    class="sidebar"
    :class="{ open, collapsed: ui.collapsed }"
    :inert="(mobile && !open) || undefined"
    :role="mobile ? 'dialog' : undefined"
    :aria-modal="(mobile && open) || undefined"
    aria-label="Navegação do workspace"
  >
    <div class="sidebar-brand">
      <RouterLink
        to="/dashboard"
        class="brand"
        aria-label="DataPulse, visão geral"
        @click="$emit('close')"
        ><span class="brand-icon"><Activity :size="23" :stroke-width="2.4" /></span
        ><span class="brand-name">DataPulse<span class="brand-dot">.</span></span></RouterLink
      ><button class="icon-button mobile-only" aria-label="Fechar menu" @click="$emit('close')">
        <X :size="18" />
      </button>
    </div>
    <div class="workspace-switch">
      <span class="workspace-mark"><Layers3 :size="17" /></span>
      <div class="sidebar-text">
        <strong>Meu workspace</strong><small>Equipe · Analytics</small>
      </div>
      <span class="workspace-shortcut sidebar-text">W</span>
    </div>
    <nav aria-label="Menu principal" @scroll="scrollTooltip">
      <template v-for="(item, index) in navigation" :key="item.path">
        <p v-if="index === 0 || item.group !== navigation[index - 1].group" class="nav-label">
          {{ item.group }}
        </p>
        <RouterLink
          :to="`/${item.path}`"
          :aria-label="item.label"
          :title="ui.collapsed ? item.label : undefined"
          @mouseenter="positionTooltip($event.currentTarget)"
          @focus="positionTooltip($event.currentTarget)"
          @click="$emit('close')"
          ><component :is="item.icon" :size="18" :stroke-width="1.7" aria-hidden="true" /><span
            class="sidebar-text"
            >{{ item.label }}</span
          ><span v-if="item.path === 'insights'" class="nav-tag sidebar-text">BETA</span
          ><span v-if="ui.collapsed" class="nav-tooltip" role="tooltip">{{
            item.label
          }}</span></RouterLink
        >
      </template>
    </nav>
    <div class="sidebar-bottom">
      <RouterLink
        to="/ingestion"
        class="sidebar-tip"
        aria-label="Importar dados"
        @click="$emit('close')"
        ><span class="tip-icon"><Activity :size="19" /></span>
        <div class="sidebar-text">
          <strong>Dê vida aos seus dados</strong>
          <p>Seu próximo insight está a uma importação de distância.</p>
          <span>Importar dados <ArrowUpRight :size="13" /></span></div
      ></RouterLink>
      <button
        class="collapse-button"
        :aria-label="ui.collapsed ? 'Expandir sidebar' : 'Recolher sidebar'"
        :aria-expanded="!ui.collapsed"
        @click="ui.collapsed = !ui.collapsed"
      >
        <component :is="ui.collapsed ? PanelLeftOpen : PanelLeftClose" :size="18" /><span
          class="sidebar-text"
          >Recolher menu</span
        ><kbd class="sidebar-text">‹</kbd>
      </button>
    </div>
  </aside>
</template>
