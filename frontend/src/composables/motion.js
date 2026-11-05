import { nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { gsap } from 'gsap'

export function useReveal(root, trigger) {
  let context
  let media
  let disposed = false
  const play = async () => {
    await nextTick()
    if (disposed || !root.value) return
    media?.revert()
    context?.revert()
    context = gsap.context(() => {
      media = gsap.matchMedia()
      media.add('(prefers-reduced-motion: no-preference)', () => {
        const targets = [...root.value.querySelectorAll('[data-reveal]')].slice(0, 14)
        if (targets.length)
          gsap.from(targets, {
            y: 14,
            opacity: 0,
            duration: 0.42,
            stagger: 0.045,
            ease: 'power2.out',
            clearProps: 'all',
          })
      })
    }, root.value)
  }
  onMounted(play)
  if (trigger) watch(trigger, play)
  onBeforeUnmount(() => {
    disposed = true
    media?.revert()
    context?.revert()
  })
}

export function pageEnter(element, done) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    done()
    return
  }
  const context = gsap.context(() => {
    gsap.from(element, {
      opacity: 0,
      y: 8,
      duration: 0.23,
      clearProps: 'all',
      onComplete: () => {
        context.revert()
        done()
      },
    })
  }, element)
}
