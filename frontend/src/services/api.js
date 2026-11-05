import axios from 'axios'

const base = (import.meta.env?.VITE_API_URL || '/api/v1').replace(/\/+$/, '')
export const docsUrl = base.replace(/\/api\/v1$/, '/docs')

export const apiClient = axios.create({ baseURL: base })

apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('datapulse-token')
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  if (config.data instanceof FormData) {
    config.headers.setContentType(false)
  } else if (config.data !== undefined) {
    config.headers.setContentType('application/json')
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (cause) => {
    if (!axios.isAxiosError(cause)) throw cause
    const response = cause.response
    let payload = response?.data
    if (payload instanceof Blob) {
      const text = await payload.text()
      try {
        payload = JSON.parse(text)
      } catch (error) {
        if (!(error instanceof SyntaxError)) throw error
        payload = null
      }
    }
    if (response?.status === 401 && !cause.config?.url?.startsWith('/auth/')) {
      globalThis.dispatchEvent(new Event('datapulse:unauthorized'))
    }
    const error = new Error(
      payload?.error?.message ||
        (response ? `Falha HTTP ${response.status}` : 'Nao foi possivel conectar a API'),
      { cause },
    )
    error.details = payload?.error?.details
    error.requestId = payload?.request_id || response?.headers.get('X-Request-ID')
    throw error
  },
)

export async function api(path, options = {}) {
  const { body, download, ...config } = options
  const response = await apiClient.request({
    ...config,
    url: path,
    data: body,
    responseType: download ? 'blob' : 'json',
  })
  return response.data
}

export const post = (path, body) => api(path, { method: 'POST', body })

export async function allPages(path) {
  const items = []
  let page = 1
  let total
  do {
    const response = await api(`${path}?page=${page}&page_size=100`)
    items.push(...response.data)
    total = response.meta.total
    page++
  } while (items.length < total)
  return items
}

export function format(value) {
  if (value === null || value === undefined) return 'Sem dados'
  if (typeof value === 'boolean') return value ? 'Sim' : 'Nao'
  if (typeof value === 'number')
    return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(value)
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
