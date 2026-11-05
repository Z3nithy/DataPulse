<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { X } from '@lucide/vue'
import { useReveal } from '@/composables/motion'
const props = defineProps({
  open: Boolean,
  title: { type: String, required: true },
  drawer: Boolean,
})
const emit = defineEmits(['close'])
const root = ref(null)
let previousFocus
useReveal(root, () => props.open)
watch(
  () => props.open,
  async (open) => {
    await nextTick()
    if (open && root.value && !root.value.open) {
      previousFocus = document.activeElement
      root.value.showModal()
    } else if (!open && root.value?.open) {
      root.value.close()
      previousFocus?.focus()
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  root.value?.close()
  previousFocus?.focus()
})
</script>
<template>
  <dialog
    ref="root"
    :class="['app-dialog', { drawer }]"
    :aria-label="title"
    @cancel.prevent="emit('close')"
    @keydown.esc.prevent.stop="emit('close')"
    @click="
      (event) => {
        if (event.target === root) emit('close')
      }
    "
  >
    <div data-reveal class="dialog-body">
      <div class="panel-heading">
        <h2>{{ title }}</h2>
        <button class="icon-button" type="button" aria-label="Fechar janela" @click="emit('close')">
          <X :size="19" />
        </button>
      </div>
      <slot />
      <div v-if="$slots.footer" class="dialog-footer"><slot name="footer" /></div>
    </div>
  </dialog>
</template>
