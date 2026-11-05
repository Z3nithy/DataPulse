import { test, expect } from '@playwright/test'
import { Buffer } from 'node:buffer'

test('real workspace: bootstrap, import, favorites, notifications, reports, automation and permissions', async ({
  page,
}) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'warning' && message.text().includes('[Vue warn]')) {
      errors.push(message.text())
    }
  })
  await page.goto('/dashboard')
  await page.getByRole('button', { name: 'Primeiro acesso? Configurar administrador' }).click()
  await page.getByRole('textbox', { name: 'Nome', exact: true }).fill('DEMO E2E Admin')
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill('e2e@example.test')
  await page.getByRole('textbox', { name: 'Senha', exact: true }).fill('Test-only-password-123')
  await page.getByRole('button', { name: 'Cadastrar administrador', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Primeiros passos no DataPulse' })).toBeVisible()

  await page.getByRole('link', { name: 'Fontes de dados', exact: true }).click()
  await page.getByRole('textbox', { name: 'Nome', exact: true }).fill('DEMO CSV')
  await page.getByRole('button', { name: 'Cadastrar fonte', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'DEMO CSV', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Datasets', exact: true }).click()
  await page.getByRole('textbox', { name: 'Nome', exact: true }).fill('DEMO Sales')
  await page
    .getByRole('combobox', { name: 'Fonte', exact: true })
    .selectOption({ label: 'DEMO CSV' })
  await page.getByRole('button', { name: 'Criar dataset', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'DEMO Sales', exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Importações', exact: true }).click()
  await page
    .getByRole('combobox', { name: 'Dataset de destino' })
    .selectOption({ label: 'DEMO Sales' })
  await page.locator('input[type=file]').setInputFiles({
    name: 'DEMO-sales.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(
      'amount,date,category\n10,2026-01-01,A\n20,2026-01-02,A\n60,2026-02-01,B\n',
    ),
  })
  await page.getByRole('button', { name: 'Importar e validar', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: 'DEMO-sales.csv' })).toContainText(
    'Concluído',
  )
  await expect(page.getByText('Worker online', { exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Analytics', exact: true }).click()
  await page
    .getByRole('combobox', { name: 'Dataset', exact: true })
    .selectOption({ label: 'DEMO Sales' })
  await page.getByRole('combobox', { name: 'Calculo', exact: true }).selectOption('sum')
  await page.getByRole('combobox', { name: 'Coluna numerica', exact: true }).selectOption('amount')
  await page.getByRole('button', { name: 'Adicionar filtro', exact: true }).click()
  await page
    .getByRole('combobox', { name: 'Coluna do filtro', exact: true })
    .selectOption('category')
  await page.getByRole('textbox', { name: 'Valor', exact: true }).fill('A')
  await page.getByRole('button', { name: 'Adicionar filtro', exact: true }).click()
  await page
    .getByRole('combobox', { name: 'Coluna do filtro', exact: true })
    .nth(1)
    .selectOption('amount')
  await page.getByRole('combobox', { name: 'Condicao', exact: true }).nth(1).selectOption('gte')
  await page.getByRole('spinbutton', { name: 'Valor', exact: true }).fill('15')
  await page.getByRole('textbox', { name: 'Nome do favorito' }).fill('DEMO Filter A')
  await page.getByRole('button', { name: 'Salvar favorito', exact: true }).click()
  await expect(page.getByRole('button', { name: 'DEMO Filter A', exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'DEMO Filter A', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Valor', exact: true })).toHaveValue('A')
  await expect(page.getByRole('spinbutton', { name: 'Valor', exact: true })).toHaveValue('15')
  await page.getByRole('button', { name: 'Executar analise', exact: true }).click()
  await expect(page.locator('.result-metrics').first()).toContainText('20')
  await page.getByRole('button', { name: 'Remover filtro', exact: true }).nth(1).click()
  await page.getByRole('button', { name: 'Executar analise', exact: true }).click()
  await expect(page.locator('.result-metrics').first()).toContainText('30')

  await page.getByRole('button', { name: /Central de notificações/ }).click()
  await expect(page.locator('#notifications-panel')).toContainText('DEMO-sales.csv')
  await page.getByRole('button', { name: 'Marcar todas como lidas', exact: true }).click()
  await expect(page.locator('#notifications-panel')).toContainText('0 não lidas')
  await page.keyboard.press('Escape')
  await expect(page.locator('#notifications-panel')).toBeHidden()
  await page.reload()
  await page.getByRole('button', { name: /Central de notificações/ }).click()
  await expect(page.locator('#notifications-panel')).toContainText('0 não lidas')
  await page.keyboard.press('Escape')

  await page.getByRole('link', { name: 'Relatórios', exact: true }).click()
  await page.getByRole('button', { name: 'DEMO Filter A', exact: true }).click()
  await page.getByRole('textbox', { name: 'Nome', exact: true }).fill('DEMO Snapshot')
  await page.getByRole('button', { name: 'Gerar relatorio', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'DEMO Snapshot', exact: true })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Exportar CSV', exact: true }).click()
  expect((await download).suggestedFilename()).toMatch(/datapulse-report-\d+\.csv/)

  await page.getByRole('textbox', { name: 'Nome do agendamento' }).fill('DEMO Scheduled Report')
  await page
    .locator('.operations-panel')
    .getByRole('combobox', { name: 'Dataset', exact: true })
    .selectOption({ label: 'DEMO Sales' })
  await page.getByRole('button', { name: 'Criar agendamento', exact: true }).click()
  const schedule = page.getByRole('row').filter({ hasText: 'DEMO Scheduled Report' })
  await expect(schedule).toBeVisible()
  await schedule.getByRole('button', { name: 'Pausar', exact: true }).click()
  await page.getByRole('button', { name: 'Confirmar agendamento', exact: true }).click()
  await expect(schedule.getByRole('button', { name: 'Retomar', exact: true })).toBeVisible()

  for (const height of [600, 767]) {
    await page.setViewportSize({ width: 1360, height })
    await page.getByRole('button', { name: 'Recolher sidebar', exact: true }).click()
    const expand = page.getByRole('button', { name: 'Expandir sidebar', exact: true })
    await expect(expand).toBeInViewport()
    await expand.click()
    await expect(page.getByRole('button', { name: 'Recolher sidebar', exact: true })).toBeVisible()
  }
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: /Central de notificações/ }).click()
  const rect = await page.locator('#notifications-panel').boundingBox()
  expect(rect.x).toBeGreaterThanOrEqual(0)
  expect(rect.x + rect.width).toBeLessThanOrEqual(390)
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Abrir ou fechar menu' }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Abrir ou fechar menu' })).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

  const api = 'http://127.0.0.1:18770/api/v1'
  const oldAdminToken = await page.evaluate(() => sessionStorage.getItem('datapulse-token'))
  await page.goto('/settings')
  await page.getByLabel('Senha atual').fill('Test-only-password-123')
  await page.getByLabel('Nova senha').fill('Another-test-password-456')
  await page.getByRole('button', { name: 'Atualizar senha', exact: true }).click()
  await expect(page.getByText('Senha atualizada. As outras sessoes foram encerradas.')).toBeVisible()
  const token = await page.evaluate(() => sessionStorage.getItem('datapulse-token'))
  expect(token).not.toBe(oldAdminToken)
  const revoked = await page.request.get(`${api}/auth/me`, {
    headers: { Authorization: 'Bearer ' + oldAdminToken },
  })
  expect(revoked.status()).toBe(401)
  const member = await page.request.post(`${api}/users`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: 'DEMO Reader', email: 'reader@example.test', password: 'Test-only-password-123' },
  })
  expect(member.status()).toBe(201)
  await page.evaluate(() => sessionStorage.removeItem('datapulse-token'))
  await page.reload()
  await page.getByRole('textbox', { name: 'Email', exact: true }).fill('reader@example.test')
  await page.getByRole('textbox', { name: 'Senha', exact: true }).fill('Test-only-password-123')
  await page.getByRole('button', { name: 'Entrar no workspace', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Configuracoes', exact: true })).toBeVisible()
  await page.goto('/reports')
  await expect(page.getByRole('heading', { name: 'Relatorios', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Gerar relatorio', exact: true })).toBeDisabled()
  await expect(page.locator('.operations-panel')).toHaveCount(0)
  const readerToken = await page.evaluate(() => sessionStorage.getItem('datapulse-token'))
  const denied = await page.request.post(`${api}/schedules`, {
    headers: { Authorization: `Bearer ${readerToken}` },
    data: { name: 'Denied', kind: 'import', dataset_id: 1, interval_minutes: 15 },
  })
  expect(denied.status()).toBe(403)
  await page.locator('.profile-dropdown summary').click()
  await page.getByRole('button', { name: 'Sair de todas as sessões', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Entrar no workspace', exact: true })).toBeVisible()
  expect(
    (
      await page.request.get(`${api}/auth/me`, {
        headers: { Authorization: 'Bearer ' + readerToken },
      })
    ).status(),
  ).toBe(401)
  expect(errors).toEqual([])
})
