import { afterEach, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { once } from 'node:events'
import { allPages, api, apiClient, docsUrl, format, post } from '../src/services/api.js'

let originalStorage
let originalDispatch
let originalBaseURL
let originalAdapter
let server
let respond
let requests
let events

beforeEach(async () => {
  originalStorage = globalThis.sessionStorage
  originalDispatch = globalThis.dispatchEvent
  originalBaseURL = apiClient.defaults.baseURL
  originalAdapter = apiClient.defaults.adapter
  globalThis.sessionStorage = { getItem: () => 'test-only-token' }
  globalThis.dispatchEvent = (event) => {
    events.push(event.type)
  }
  requests = []
  events = []
  respond = (_request, response) => {
    response.setHeader('Content-Type', 'application/json')
    response.end(JSON.stringify({ data: { id: 7 }, meta: {} }))
  }
  server = createServer(async (request, response) => {
    const chunks = []
    for await (const chunk of request) chunks.push(chunk)
    const body = Buffer.concat(chunks).toString('utf8')
    requests.push({ url: request.url, method: request.method, headers: request.headers, body })
    respond(request, response)
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  apiClient.defaults.baseURL = `http://127.0.0.1:${server.address().port}/api/v1`
  // Use Axios's browser-compatible Fetch adapter so Node also exercises Blob responses.
  apiClient.defaults.adapter = 'fetch'
})

afterEach(async () => {
  apiClient.defaults.baseURL = originalBaseURL
  apiClient.defaults.adapter = originalAdapter
  globalThis.sessionStorage = originalStorage
  globalThis.dispatchEvent = originalDispatch
  const closed = new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()))
  })
  server.closeAllConnections()
  await closed
})

function respondJson(payload, status = 200) {
  respond = (_request, response) => {
    response.writeHead(status, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify(payload))
  }
}

test('JSON requests use Axios, the real API contract and bearer header', async () => {
  assert.deepEqual(await post('/sources', { name: 'Test', kind: 'csv' }), {
    data: { id: 7 },
    meta: {},
  })
  assert.equal(requests[0].url, '/api/v1/sources')
  assert.equal(requests[0].method, 'POST')
  assert.equal(docsUrl, '/docs')
  assert.equal(requests[0].headers.authorization, 'Bearer test-only-token')
  assert.equal(requests[0].headers['content-type'], 'application/json')
  assert.deepEqual(JSON.parse(requests[0].body), { name: 'Test', kind: 'csv' })
})

test('existing PATCH callers can still send serialized JSON and custom headers', async () => {
  await api('/datasets/1', {
    method: 'PATCH',
    body: JSON.stringify({ name: 'Updated', source_id: null }),
    headers: { 'X-Test': 'preserved' },
  })
  assert.equal(requests[0].method, 'PATCH')
  assert.equal(requests[0].headers['x-test'], 'preserved')
  assert.deepEqual(JSON.parse(requests[0].body), { name: 'Updated', source_id: null })
})

test('uploads preserve multipart boundaries and file contents', async () => {
  const form = new FormData()
  form.append('dataset_id', '1')
  form.append('file', new Blob(['amount\n42\n'], { type: 'text/csv' }), 'data.csv')
  await api('/ingestion/import', { method: 'POST', body: form })
  const request = requests[0]
  const boundary = request.headers['content-type'].match(/^multipart\/form-data; boundary=(.+)$/)
  assert.ok(boundary, request.headers['content-type'])
  assert.ok(request.body.includes(`--${boundary[1]}`))
  assert.match(request.body, /name="dataset_id"\r\n\r\n1/)
  assert.match(request.body, /filename="data.csv"/)
  assert.match(request.body, /amount\n42\n/)
})

test('requests read the current token rather than caching stale credentials', async () => {
  globalThis.sessionStorage = { getItem: () => null }
  await api('/auth/setup')
  assert.equal(requests[0].headers.authorization, undefined)
  globalThis.sessionStorage = { getItem: () => 'updated-test-token' }
  await api('/datasets')
  assert.equal(requests[1].headers.authorization, 'Bearer updated-test-token')
})

test('errors preserve validation details and the request identifier', async () => {
  respondJson(
    {
      error: { message: 'Dados invalidos', details: [{ message: 'Coluna desconhecida' }] },
      request_id: 'request-123',
    },
    422,
  )
  await assert.rejects(api('/analytics/query'), (error) => {
    assert.equal(error.message, 'Dados invalidos')
    assert.equal(error.requestId, 'request-123')
    assert.equal(error.details[0].message, 'Coluna desconhecida')
    return true
  })
})

test('expired protected requests notify the session, login failures do not', async () => {
  respondJson({ error: { message: 'Sessao expirada' } }, 401)
  await assert.rejects(api('/datasets'))
  await assert.rejects(post('/auth/login', { email: 'invalid', password: 'invalid' }))
  assert.deepEqual(events, ['datapulse:unauthorized'])
})

test('lookup lists traverse pagination instead of silently truncating data', async () => {
  respond = (_request, response) => {
    response.setHeader('Content-Type', 'application/json')
    response.end(
      JSON.stringify({
        data: requests.length === 1 ? [{ id: 1 }] : [{ id: 2 }],
        meta: { total: 2 },
      }),
    )
  }
  assert.deepEqual(await allPages('/datasets'), [{ id: 1 }, { id: 2 }])
  assert.equal(requests[1].url, '/api/v1/datasets?page=2&page_size=100')
})

test('report export returns a Blob, never tries to decode CSV as JSON', async () => {
  respond = (_request, response) => {
    response.setHeader('Content-Type', 'text/csv')
    response.end('grupo,valor\nA,42')
  }
  const blob = await api('/reports/1/export', { download: true })
  assert.ok(blob instanceof Blob)
  assert.match(await blob.text(), /A,42/)
})

test('download errors decode JSON Blob responses and notify expired sessions', async () => {
  respondJson(
    {
      error: { message: 'Sessao expirada', details: { reason: 'expired' } },
      request_id: 'download-123',
    },
    401,
  )
  await assert.rejects(api('/reports/1/export', { download: true }), (error) => {
    assert.equal(error.message, 'Sessao expirada')
    assert.equal(error.requestId, 'download-123')
    assert.deepEqual(error.details, { reason: 'expired' })
    return true
  })
  assert.deepEqual(events, ['datapulse:unauthorized'])
})

test('non-JSON HTTP errors remain explicit for regular and download requests', async () => {
  respond = (_request, response) => {
    response.writeHead(502, { 'Content-Type': 'text/html', 'X-Request-ID': 'proxy-123' })
    response.end('<h1>Bad gateway</h1>')
  }
  for (const options of [{}, { download: true }]) {
    await assert.rejects(api('/reports/1/export', options), (error) => {
      assert.equal(error.message, 'Falha HTTP 502')
      assert.equal(error.requestId, 'proxy-123')
      return true
    })
  }
})

test('network failures surface a connection error without logging the user out', async () => {
  respond = (request) => request.socket.destroy()
  await assert.rejects(api('/datasets'), { message: 'Nao foi possivel conectar a API' })
  assert.deepEqual(events, [])
})

test('empty statistical results are not presented as zero', () => {
  assert.equal(format(null), 'Sem dados')
  assert.equal(format(undefined), 'Sem dados')
  assert.equal(format(0), '0')
  assert.equal(format(false), 'Nao')
  assert.equal(format({ field: 'category' }), '{"field":"category"}')
})
