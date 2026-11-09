<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { gsap } from 'gsap'

defineOptions({ name: 'NeuralWavesBackground' })

const canvas = ref(null)
const layerCount = 5
const rowsPerLayer = 24
const columns = 156
const starsCount = 88
let gl
let program
let positionBuffer
let timeLocation
let pixelRatio = 1
let resizeObserver
let motionContext
let animation
let clock
let vertexCount = 0
let themeObserver

const vertexShader = `
  precision mediump float;
  attribute vec3 a_point;
  uniform float u_time;
  uniform float u_pixel_ratio;
  uniform float u_light_theme;
  varying float v_alpha;

  void main() {
    float x = a_point.x;
    float row = a_point.y;
    float layer = a_point.z;

    if (layer < 0.0) {
      gl_Position = vec4(x, row, 0.0, 1.0);
      gl_PointSize = 2.4 * u_pixel_ratio;
      v_alpha = 0.3;
    } else {
      float first = sin(x * 7.4 + row * 4.2 + u_time + layer * 0.9);
      float second = sin(x * 14.8 - row * 3.1 + u_time * 2.0 + layer * 0.75);
      float amplitude = 0.085 + (1.0 - abs(row)) * 0.17;
      float wave = first * amplitude + second * 0.065;
      float y = 0.04 - layer * 0.13 + row * 0.09 + wave;
      float perspective = 1.0 - abs(row) * 0.62;
      float crest = 0.5 + 0.5 * first;

      gl_Position = vec4(x + row * 0.2, y, 0.0, 1.0);
      gl_PointSize = (1.5 + perspective * 1.45 + crest * 0.65) * u_pixel_ratio;
      v_alpha = (0.25 + crest * 0.62) * perspective * (1.0 - layer * 0.075);
      v_alpha *= mix(1.0, 1.32, u_light_theme);
    }
  }
`

const fragmentShader = `
  precision mediump float;
  uniform float u_light_theme;
  varying float v_alpha;

  void main() {
    vec2 point = gl_PointCoord - vec2(0.5);
    float distanceFromCenter = length(point);
    float core = 1.0 - smoothstep(0.12, 0.48, distanceFromCenter);
    float glow = exp(-distanceFromCenter * 9.0) * 0.34;
    float alpha = v_alpha * (core * 0.78 + glow);
    vec3 dark_color = vec3(0.2, 0.78, 1.0);
    vec3 light_color = vec3(0.0, 0.26, 0.38);
    gl_FragColor = vec4(mix(dark_color, light_color, u_light_theme), alpha);
  }
`

function compileShader(type, source) {
  const shader = gl.createShader(type)
  if (!shader) throw new Error('Nao foi possivel criar o shader do fundo animado.')

  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader)
    gl.deleteShader(shader)
    throw new Error(`Falha ao compilar o shader do fundo animado: ${message}`)
  }

  return shader
}

function createProgram() {
  const vertex = compileShader(gl.VERTEX_SHADER, vertexShader)
  const fragment = compileShader(gl.FRAGMENT_SHADER, fragmentShader)
  const nextProgram = gl.createProgram()
  if (!nextProgram) throw new Error('Nao foi possivel criar o programa do fundo animado.')

  gl.attachShader(nextProgram, vertex)
  gl.attachShader(nextProgram, fragment)
  gl.linkProgram(nextProgram)
  gl.deleteShader(vertex)
  gl.deleteShader(fragment)

  if (!gl.getProgramParameter(nextProgram, gl.LINK_STATUS)) {
    const message = gl.getProgramInfoLog(nextProgram)
    gl.deleteProgram(nextProgram)
    throw new Error(`Falha ao vincular o shader do fundo animado: ${message}`)
  }

  return nextProgram
}

function createPoints() {
  const points = []
  for (let layer = 0; layer < layerCount; layer += 1) {
    for (let row = 0; row < rowsPerLayer; row += 1) {
      const depth = (row / (rowsPerLayer - 1)) * 2 - 1
      for (let column = 0; column < columns; column += 1) {
        const x = (column / (columns - 1)) * 2 - 1
        points.push(x, depth, layer)
      }
    }
  }

  for (let index = 0; index < starsCount; index += 1) {
    const xSeed = Math.sin((index + 1) * 127.1) * 43758.5453
    const ySeed = Math.sin((index + 1) * 269.5) * 24634.6345
    const x = (xSeed - Math.floor(xSeed)) * 2 - 1
    const y = 0.2 + (ySeed - Math.floor(ySeed)) * 0.75
    points.push(x, y, -1)
  }

  return new Float32Array(points)
}

function resize() {
  if (!canvas.value || !gl) return

  const { width, height } = canvas.value.getBoundingClientRect()
  pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5)
  canvas.value.width = Math.round(width * pixelRatio)
  canvas.value.height = Math.round(height * pixelRatio)
  gl.viewport(0, 0, canvas.value.width, canvas.value.height)
  gl.uniform1f(gl.getUniformLocation(program, 'u_pixel_ratio'), pixelRatio)
  render()
}

function render() {
  if (!gl || !program) return

  gl.clear(gl.COLOR_BUFFER_BIT)
  gl.uniform1f(timeLocation, clock?.value ?? 0)
  gl.drawArrays(gl.POINTS, 0, vertexCount)
}

function updateTheme() {
  if (!gl || !program) return

  gl.useProgram(program)
  const isLight = document.documentElement.dataset.theme === 'light'
  gl.uniform1f(
    gl.getUniformLocation(program, 'u_light_theme'),
    isLight ? 1 : 0,
  )
  gl.blendFunc(gl.SRC_ALPHA, isLight ? gl.ONE_MINUS_SRC_ALPHA : gl.ONE)
  render()
}

onMounted(() => {
  gl = canvas.value.getContext('webgl', { alpha: true, antialias: true })
  if (!gl) throw new Error('WebGL nao esta disponivel para renderizar o fundo animado.')

  program = createProgram()
  gl.useProgram(program)
  timeLocation = gl.getUniformLocation(program, 'u_time')
  updateTheme()
  positionBuffer = gl.createBuffer()
  if (!positionBuffer) throw new Error('Nao foi possivel criar a malha do fundo animado.')

  const points = createPoints()
  vertexCount = points.length / 3
  gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer)
  gl.bufferData(gl.ARRAY_BUFFER, points, gl.STATIC_DRAW)

  const positionLocation = gl.getAttribLocation(program, 'a_point')
  gl.enableVertexAttribArray(positionLocation)
  gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0)
  gl.clearColor(0, 0, 0, 0)
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE)

  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(canvas.value)
  themeObserver = new MutationObserver(updateTheme)
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
  resize()

  motionContext = gsap.matchMedia()
  motionContext.add('(prefers-reduced-motion: no-preference)', () => {
    clock = { value: 0 }
    animation = gsap.to(clock, {
      value: Math.PI * 2,
      duration: 18,
      ease: 'none',
      repeat: -1,
    })
    gsap.ticker.add(render)

    return () => {
      gsap.ticker.remove(render)
      animation?.kill()
      animation = undefined
      clock = undefined
    }
  })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  themeObserver?.disconnect()
  motionContext?.revert()
  if (positionBuffer) gl?.deleteBuffer(positionBuffer)
  if (program) gl?.deleteProgram(program)
})
</script>

<template>
  <canvas ref="canvas" class="neural-background" aria-hidden="true" />
</template>

<style>
.neural-background {
  position: fixed;
  inset: 0;
  z-index: 0;
  display: block;
  width: 100%;
  height: 100dvh;
  opacity: 0.58;
  pointer-events: none;
}

[data-theme='light'] .neural-background {
  opacity: 0.72;
}
</style>
