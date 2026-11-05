<script setup>
defineOptions({ name: 'AppNotification' })
import { ref } from 'vue'
import { CircleCheck, CircleAlert, Info, X } from '@lucide/vue'
import { useReveal } from '@/composables/motion'
const props = defineProps({
  message: { type: String, required: true },
  kind: { type: String, default: 'info' },
})
defineEmits(['dismiss'])
const root = ref(null)
useReveal(root, () => props.message)
</script>
<template>
  <div ref="root">
    <div
      v-if="message"
      data-reveal
      :role="kind === 'error' ? 'alert' : 'status'"
      class="message"
      :class="kind"
    >
      <component
        :is="kind === 'error' ? CircleAlert : kind === 'success' ? CircleCheck : Info"
        :size="18"
        aria-hidden="true"
      />
      <span>{{ message }}</span
      ><button
        type="button"
        class="icon-button"
        aria-label="Fechar mensagem"
        @click="$emit('dismiss')"
      >
        <X :size="16" />
      </button>
    </div>
  </div>
</template>
