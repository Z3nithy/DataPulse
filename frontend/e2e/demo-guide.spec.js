import { test, expect } from '@playwright/test'

test('demo guide shows shared credentials and fills the login form', async ({ page }) => {
  await page.route('**/api/v1/auth/demo', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          available: true,
          username: 'portfolio',
          password: 'Demo-password-123',
          role: 'editor',
        },
      }),
    }),
  )

  await page.goto('/dashboard')
  await expect(page.getByRole('textbox', { name: 'Usuário' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Email' })).toHaveCount(0)
  await page.getByRole('button', { name: 'GUIA' }).click()

  const dialog = page.getByRole('dialog', { name: 'Acesso de demonstração' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('portfolio', { exact: true })).toBeVisible()
  await expect(dialog.getByText('Demo-password-123')).toBeVisible()
  await expect(
    dialog.getByText('Esta conta é compartilhada. Não use dados reais ou confidenciais.'),
  ).toBeVisible()

  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'])
  await dialog.getByRole('button', { name: 'Copiar usuário' }).click()
  await expect(dialog.getByRole('button', { name: 'Usuário copiado' })).toHaveText('Copiado')
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe('portfolio')

  await dialog.getByRole('button', { name: 'Preencher acesso demo' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Usuário' })).toHaveValue('portfolio')
  await expect(page.getByRole('textbox', { name: 'Senha' })).toHaveValue('Demo-password-123')
})

test('login offers an optional product tour that can be reopened later', async ({ page }) => {
  await page.route('**/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    let data = []
    let meta = { page: 1, page_size: 100, total: 0, unread: 0 }
    if (url.pathname.endsWith('/auth/demo')) {
      data = {
        available: true,
        username: 'portfolio',
        password: 'Demo-password-123',
        role: 'editor',
      }
    } else if (url.pathname.endsWith('/auth/setup')) {
      data = { registration_open: false }
    } else if (url.pathname.endsWith('/auth/login')) {
      data = {
        user: {
          id: 44,
          name: 'Tour User',
          username: 'portfolio',
          email: 'portfolio@example.test',
          role: 'editor',
        },
        access_token: 'tour-test-token',
        token_type: 'bearer',
      }
    } else if (url.pathname.endsWith('/analytics/summary')) {
      data = {
        records: 0,
        sources: 0,
        datasets: 0,
        imports: 0,
        user_imports: 0,
        analytics_queries: 0,
        reports: 0,
        kpi_count: 0,
        kpis: [],
        active_alerts: 0,
        recent_jobs: [],
        insights: [],
        recent_alerts: [],
      }
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data, meta }),
    })
  })
  await page.goto('/settings')
  await page.getByRole('button', { name: 'GUIA' }).click()
  await page.getByRole('button', { name: 'Preencher acesso demo' }).click()
  await page.getByRole('button', { name: 'Entrar no workspace', exact: true }).click()

  const invite = page.getByRole('dialog', { name: 'Conheça o DataPulse' })
  await expect(invite).toBeVisible()
  await expect(invite).toContainText('opcional')
  await invite.getByRole('button', { name: 'Começar tour' }).click()

  const tour = page.locator('.product-tour-tooltip')
  const sections = [
    'Visão geral',
    'Fontes de dados',
    'Datasets',
    'Importações',
    'Analytics',
    'Tendências',
    'KPIs',
    'Alertas',
    'Insights',
    'Relatórios',
    'Configurações',
  ]
  for (const [index, section] of sections.entries()) {
    await expect(tour.getByText(section, { exact: true })).toBeVisible()
    await expect(page.locator('.product-tour-spotlight')).toBeVisible()
    if (index < sections.length - 1) {
      await tour.getByRole('button', { name: 'Próximo' }).click()
    }
  }
  await tour.getByRole('button', { name: 'Concluir' }).click()
  await expect(tour).not.toBeVisible()

  await page.locator('.profile-dropdown summary').click()
  await page.getByRole('button', { name: 'Fazer tour do sistema' }).click()
  await expect(page.locator('.product-tour-tooltip')).toContainText('Leia o resumo do workspace')
  await page.locator('.product-tour-tooltip').getByRole('button', { name: 'Sair do tour' }).click()
  await page.locator('.profile-dropdown summary').click()
  await page.getByRole('button', { name: 'Sair de todas as sessões' }).click()
  await expect(page.getByRole('textbox', { name: 'Usuário', exact: true })).toBeVisible()
})
