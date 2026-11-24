import { test, expect } from '@playwright/test'
import { acceptConsent } from './helpers.js'

test('davet, onaylı aktarım, kişi karşılaştırması ve bir koltuk için tek oy', async ({page, browser}) => {
  await acceptConsent(page)
  let routes = 0
  page.on('request', r => { if (r.url().endsWith('/routes/matrix')) routes++ })
  await page.goto('/')
  await page.getByLabel('Grup', {exact:true}).fill('2')
  await page.getByText('Katılımcı davetleri ve oylama',{exact:true}).click()
  await page.getByRole('button',{name:'2 kişilik davet oluştur'}).click()
  const guests = []
  try {
    for(let i=0;i<2;i++) {
      const url=await page.getByLabel('Kişi '+(i+1)+' davet bağlantısı',{exact:true}).inputValue()
      const guest=await browser.newPage(); await acceptConsent(guest)
      guests.push(guest)
      await guest.goto(url)
      await guest.getByLabel('Başlangıç koordinatı').fill(i?'39.93,32.86':'39.92,32.85')
      await expect(guest.getByRole('button',{name:'Başlangıç noktamı kaydet'})).toBeDisabled()
      await guest.getByRole('checkbox').check()
      await guest.getByRole('button',{name:'Başlangıç noktamı kaydet'}).click()
      await expect(guest.getByText('Başlangıç noktanız kaydedildi.')).toBeVisible()
    }
    await page.getByRole('button',{name:'Davet durumunu yenile'}).click()
    await page.getByRole('button',{name:'Başlangıç noktalarını kullan'}).click()
    await expect(page.getByLabel('Link veya koordinat',{exact:true}).first()).toHaveValue('39.92,32.85')
    expect(routes).toBe(0)
    await page.getByRole('button',{name:'Öneri üret',exact:true}).click()
    await expect(page.locator('.recommendation-card')).toHaveCount(3)
    await page.getByText('İki mekânı karşılaştır',{exact:true}).click()
    await page.getByRole('combobox',{name:'B mekânı',exact:true}).selectOption({index:1})
    await expect(page.locator('.comparison dl > div')).toHaveCount(4)
    await page.getByRole('button',{name:'Sonuçları oylamaya aç'}).click()
    await expect(page.getByRole('heading',{name:'Grup oyları'})).toBeVisible()
    await guests[0].getByRole('button',{name:'Durumu yenile'}).click()
    await guests[0].getByRole('button',{name:/için oy ver/}).first().click()
    await expect(guests[0].getByRole('button',{pressed:true})).toHaveCount(1)
    await guests[0].getByRole('button',{name:/için oy ver/}).last().click()
    await expect(guests[0].getByText('1 oy',{exact:true})).toHaveCount(1)
    expect(routes).toBe(1)
    await page.getByRole('button',{name:'Daveti kapat'}).click()
    await guests[0].getByRole('button',{name:'Durumu yenile'}).click()
    await expect(guests[0].getByRole('status')).toContainText('geçersiz')
  } finally { for(const g of guests) await g.close() }
})
