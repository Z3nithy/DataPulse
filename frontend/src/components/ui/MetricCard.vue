<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { ArrowUpRight } from '@lucide/vue'
import { format } from '@/services/api'
const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: null },
  note: { type: String, default: '' },
  icon: { type: [Object, Function], required: true },
  tone: { type: String, default: 'indigo' },
  to: { type: String, default: '/analytics' },
})
const root = ref(null)
const displayed = ref(props.value)
let context
let media
function animate(value) {
  media?.revert()
  context?.revert()
  displayed.value = value
  if (!root.value || value === null) return
  context = gsap.context(() => {
    media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      const state = { value: 0 }
      gsap.to(state, {
        value,
        duration: 0.65,
        ease: 'power2.out',
        onUpdate: () => {
          displayed.value = Math.round(state.value)
        },
        onComplete: () => {
          displayed.value = value
        },
      })
      return () => {
        displayed.value = value
      }
    })
  }, root.value)
}
watch(() => props.value, animate, { flush: 'post' })
onMounted(() => animate(props.value))
onBeforeUnmount(() => {
  media?.revert()
  context?.revert()
})
</script>
<template>
  <article ref="root" class="metric" :class="`tone-${tone}`" data-reveal>
    <RouterLink :to="to" class="metric-link">
      <div class="metric-top">
        <span class="metric-icon"><component :is="icon" :size="18" aria-hidden="true" /></span
        ><ArrowUpRight :size="15" class="metric-arrow" aria-hidden="true" />
      </div>
      <span>{{ label }}</span
      ><strong aria-hidden="true">{{ format(displayed) }}</strong
      ><span class="sr-only">{{ format(value) }}</span
      ><small>{{ note }}</small>
    </RouterLink>
  </article>
</template>
