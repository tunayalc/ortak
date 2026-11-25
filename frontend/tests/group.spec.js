import { test, expect } from '@playwright/test'
import { acceptConsent } from './helpers.js'

test('oda: tek bağlantı, adla katılım, yer arama ve cihaz konumu, aktarım, oylama, kaydetme', async ({ page, browser }) => {
  await acceptConsent(page)
  let routes = 0
  page.on('request', r => { if (r.url().endsWith('/routes/matrix')) routes++ })
  await page.goto('/')
  await page.getByRole('button', { name: 'Oda kur', exact: true }).click()
  await page.getByLabel('Oda adı', { exact: true }).fill('Cuma ekibi')
  await page.getByRole('button', { name: 'Oda kur', exact: true }).last().click()
  await expect(page.getByText('Henüz kimse katılmadı. Bağlantıyı paylaşın.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('href', /^https:\/\/wa\.me\/\?text=/)
  const link = await page.getByLabel('Oda bağlantısı', { exact: true }).inputValue()
  expect(link).toMatch(/#oda=[A-Za-z0-9_-]{43}$/)

  const guests = []
  try {
    // Guest 1 searches by text (a coordinate works without a Google key in tests).
    const first = await browser.newPage(); guests.push(first); await acceptConsent(first)
    await first.goto(link)
    await first.getByLabel('Adınız', { exact: true }).fill('Ayşe')
    await first.getByRole('button', { name: 'Odaya katıl' }).click()
    await expect(first.getByText('Cuma ekibi · Ayşe')).toBeVisible()
    await expect(first.getByRole('checkbox')).toHaveCount(0)
    await expect(first.getByRole('button', { name: 'Başlangıç noktamı kaydet' })).toBeDisabled()
    await first.getByLabel('Başlangıç noktanız', { exact: true }).fill('39.92,32.85')
    await first.getByRole('button', { name: 'Ara', exact: true }).click()
    await first.getByRole('list', { name: 'Yer arama sonuçları' }).getByRole('button').first().click()
    await first.getByLabel('Nasıl geleceksiniz?').selectOption('transit')
    await first.getByRole('button', { name: 'Başlangıç noktamı kaydet' }).click()
    await expect(first.getByText(/Başlangıç noktanız kaydedildi \(Toplu taşıma\)/)).toBeVisible()

    // Guest 2 uses the device location.
    const context = await browser.newContext({ geolocation: { latitude: 39.93, longitude: 32.86 }, permissions: ['geolocation'] })
    const second = await context.newPage(); guests.push(second); await acceptConsent(second)
    await second.goto(link)
    await second.getByLabel('Adınız', { exact: true }).fill('Burak')
    await second.getByRole('button', { name: 'Odaya katıl' }).click()
    await second.getByRole('button', { name: 'Konumum', exact: true }).click()
    await expect(second.getByText('Seçilen: Bulunduğum konum')).toBeVisible()
    await second.getByRole('button', { name: 'Başlangıç noktamı kaydet' }).click()
    await expect(second.getByText(/Başlangıç noktanız kaydedildi/)).toBeVisible()
    // Reloading keeps the seat; no second join is needed.
    await second.reload()
    await expect(second.getByText('Cuma ekibi · Burak')).toBeVisible()

    await expect(page.getByText('Katılanlar (2/8) · Konum ekleyen: 2')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('Konum eklendi · Toplu taşıma')).toBeVisible()
    await page.getByRole('button', { name: 'Konumları kişi listesine aktar' }).click()
    const labels = page.locator('.participant-row label:has-text("Kişi") input').first()
    await expect(labels).toHaveValue('Ayşe')
    await expect(page.getByLabel('Yer adı, link veya koordinat', { exact: true })).toHaveCount(2)
    await expect(page.getByLabel('Yer adı, link veya koordinat', { exact: true }).nth(1)).toHaveValue('39.93,32.86')
    expect(routes).toBe(0)
    await page.getByRole('button', { name: 'Öneri üret', exact: true }).click()
    await expect(page.locator('.recommendation-card')).toHaveCount(3)
    await page.getByRole('button', { name: 'Sonuçları odada oylamaya aç' }).click()
    await expect(page.getByRole('heading', { name: 'Grup oyları' })).toBeVisible()
    await first.getByRole('button', { name: 'Durumu yenile' }).click()
    await first.getByRole('button', { name: /için oy ver/ }).first().click()
    await expect(first.getByRole('button', { pressed: true })).toHaveCount(1)
    expect(routes).toBe(1)

    // Save the room, end the meeting, reopen it from the saved list.
    await page.getByLabel('Sık buluşuyorsanız odayı kaydedin').fill('Cuma ekibi')
    await page.getByRole('button', { name: 'Odayı kaydet' }).click()
    await expect(page.getByText('Kayıtlı', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Bu buluşmayı bitir' }).click()
    await expect(page.getByRole('heading', { name: 'Kayıtlı odalarım' })).toBeVisible()
    await page.getByRole('button', { name: 'Aç', exact: true }).click()
    await expect(page.getByText('Katılanlar (2/8) · Konum ekleyen: 0')).toBeVisible()
    expect(await page.getByLabel('Oda bağlantısı', { exact: true }).inputValue()).toBe(link)
    await first.reload()
    await expect(first.getByText('Cuma ekibi · Ayşe')).toBeVisible()
    await expect(first.getByRole('button', { name: 'Başlangıç noktamı kaydet' })).toBeVisible()

    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: 'Bu buluşmayı bitir' }).click()
    await page.getByRole('button', { name: 'Cuma ekibi kaydını sil' }).click()
    await expect(page.getByText('Oda kaydı silindi.')).toBeVisible()
    await first.getByRole('button', { name: 'Durumu yenile' }).click()
    await expect(first.getByRole('button', { name: 'Odaya katıl' })).toBeVisible()
  } finally { for (const g of guests) await g.close() }
})

test('kişi satırında yer adıyla arama sonucu seçilir', async ({ page }) => {
  await acceptConsent(page)
  await page.route('**/api/locations/search', route => route.fulfill({ json: [
    { name: 'Mogan Gölü', address: 'Gölbaşı/Ankara', lat: 39.773, lng: 32.79 },
    { name: 'Mogan Parkı', address: 'Gölbaşı/Ankara', lat: 39.78, lng: 32.8 },
  ] }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Konumları ben gireyim' }).click()
  const field = page.getByLabel('Yer adı, link veya koordinat', { exact: true }).first()
  await field.fill('Mogan Gölü')
  await field.press('Enter')
  await page.getByRole('button', { name: /Mogan Gölü/ }).click()
  await expect(field).toHaveValue('39.773,32.79')
  await expect(page.getByText('Seçilen: Mogan Gölü (Gölbaşı/Ankara)')).toBeVisible()
  await expect(page.getByText('Google Maps', { exact: true })).toHaveCount(0)
})
