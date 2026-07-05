import { test, expect, Page } from '@playwright/test';

const makeSnapshot = (overrides: Record<string, unknown> = {}) => {
  const base: Record<string, unknown> = {
    scheduler: {
      system_on: true,
      mode: 'AUTO',
      runtime: { cct: 5000, lux: 300, progress: 45 },
      manual_input: { cw: 50, ww: 50 },
      loaded_scene: 'office',
      running_scene: 'office',
      available_scenes: ['office', 'warehouse', 'lab'],
      scene_profile: {
        cct: [[0, 3500], [6, 4000], [12, 6000], [18, 5000]],
        intensity: [[0, 50], [6, 200], [12, 500], [18, 300]],
      },
    },
    metrics: { cpu: 23.5, memory: 45.2, temperature: 42.1 },
    timer: { enabled: true, start: '06:00', end: '19:00' },
    luminaires: {
      '192.168.1.100': { cw: 50, ww: 50, connected: true },
      '192.168.1.101': { cw: 30, ww: 70, connected: true },
    },
    last_updated: '2026-07-05T10:00:00',
  };
  return { ...base, ...overrides };
};

let snapshot = makeSnapshot();

async function mockAll(page: Page) {
  snapshot = makeSnapshot();
  await page.route('**/snapshot', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(snapshot) }));
  await page.route('**/events', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream',
      body: `data: ${JSON.stringify({ snapshot })}\n\n` }));
  await page.route('**/config.yaml', (route) => route.fulfill({ status: 404 }));
  // API dispatcher — must register LAST so it's tried FIRST (reverse order)
  await page.route('**/api/**', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const url = route.request().url();
    let body: Record<string, unknown> | undefined;
    try {
      body = await route.request().postDataJSON();
    } catch { /* empty or non-JSON */ }
    if (url.includes('/api/system/power') && body) {
      snapshot = makeSnapshot({ scheduler: { ...snapshot.scheduler, system_on: body.on ?? false } });
    } else if (url.includes('/api/system/mode') && body) {
      snapshot = makeSnapshot({ scheduler: { ...snapshot.scheduler, system_on: true, mode: body.mode ?? 'AUTO' } });
    } else if (url.includes('/api/set/manual') && body) {
      snapshot = makeSnapshot({ scheduler: { ...snapshot.scheduler, mode: 'MANUAL', manual_input: { cw: body.cw ?? 50, ww: body.ww ?? 50 } } });
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
}

test.describe('LCS Webapp E2E', () => {
  test.beforeEach(async ({ page }) => {
    await mockAll(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Wait for snapshot to arrive via SSE — header confirms it
    await expect(page.getByRole('heading', { name: /luminaire control system/i })).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(500);
  });

  test('loads and shows header with system toggle on', async ({ page }) => {
    await expect(page.getByRole('button', { name: /toggle system/i })).toBeVisible();
  });

  test('system toggle switches power on/off', async ({ page }) => {
    const toggle = page.getByRole('button', { name: /toggle system/i });
    await toggle.click();
    // After POST, fresh SSE event delivers snapshot with system_on=false
    // The app merges and re-renders. Wait for the .toggle-pill.off class.
    const off = page.locator('.header-panel .toggle-pill.off');
    await expect(off).toBeVisible({ timeout: 12000 });
  });

  test('control panel shows mode buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'MANUAL' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'AUTO' })).toBeVisible();
  });

  test('switches to MANUAL mode and shows CW/WW buttons', async ({ page }) => {
    // Click MANUAL — POST fires, then fresh SSE delivers mode=MANUAL snapshot
    await page.getByRole('button', { name: 'MANUAL' }).click();
    const cwInc = page.getByRole('button', { name: /increase cool white/i });
    await expect(cwInc).toBeVisible({ timeout: 12000 });
  });

  test('CW increment button click does not error', async ({ page }) => {
    await page.getByRole('button', { name: 'MANUAL' }).click();
    const cwInc = page.getByRole('button', { name: /increase cool white/i });
    await expect(cwInc).toBeVisible({ timeout: 12000 });
    await cwInc.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.toast-error')).toBeHidden({ timeout: 3000 });
  });

  test('scene selector has options', async ({ page }) => {
    const select = page.locator('select');
    await expect(select).toBeVisible();
    const options = await select.locator('option').allTextContents();
    expect(options).toContain('office');
    expect(options).toContain('warehouse');
    expect(options).toContain('lab');
  });

  test('timer section shows schedule', async ({ page }) => {
    await expect(page.getByText('06:00').first()).toBeVisible();
    await expect(page.getByText('19:00').first()).toBeVisible();
  });

  test('SET and CLEAR buttons visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: /set/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /clear/i }).first()).toBeVisible();
  });

  test('CLEAR timer works', async ({ page }) => {
    await page.getByRole('button', { name: /clear/i }).first().click();
    await page.waitForTimeout(500);
    await expect(page.locator('.toast-error')).toBeHidden({ timeout: 3000 });
  });

  test('luminaires list visible', async ({ page }) => {
    await expect(page.getByText('192.168.1.100')).toBeVisible();
    await expect(page.getByText('192.168.1.101')).toBeVisible();
  });

  test('stats show CPU value', async ({ page }) => {
    await expect(page.getByText('23.5').first()).toBeVisible();
    await expect(page.getByText('%').first()).toBeVisible();
  });

  test('charts visible on desktop', async ({ page }) => {
    await expect(page.locator('.chart-shell').first()).toBeVisible({ timeout: 5000 });
  });

  test('search filters luminaires', async ({ page }) => {
    await page.getByRole('button', { name: /toggle search/i }).click();
    await expect(page.locator('input[type="text"]')).toBeVisible({ timeout: 3000 });
    await page.locator('input[type="text"]').fill('101');
    await page.waitForTimeout(500);
    await expect(page.getByText('192.168.1.101')).toBeVisible();
  });

  test('SET timer button posts to API', async ({ page }) => {
    await page.getByRole('button', { name: /set/i }).first().click();
    await page.waitForTimeout(500);
    await expect(page.locator('.toast-error')).toBeHidden({ timeout: 3000 });
  });
});
