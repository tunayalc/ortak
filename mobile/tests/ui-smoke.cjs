async (page) => {
  // Playwright CLI fixture run only. These are NOT live Google or Llama results.
  const counts = {};
  const checks = [];
  let lastRecommendation;
  let lastScenario;
  let capacity = true;
  let partial = false;
  let recommendFails = false;
  let deleteFails = false;
  const people = [1, 2, 3].map(i => ({ id: `user-${i}`, label: `Kişi ${i}`, delta_weight: 1 }));
  const candidates = [1, 2, 3].map(i => ({ id: `p${i}`, place_id: `test-place-${i}`, name: `Test Kafe ${i}`, address: 'Kurgusal test adresi', rating: 4 + i / 10, review_count: i * 10, price_level: i === 1 ? null : i, provider: 'google', attributions: [] }));
  const scenario = { id: 'test-scenario', city: 'Ankara', category: 'cafe', session_only: true, users: people };
  const fulfill = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data), headers: { 'Access-Control-Allow-Origin': 'http://localhost:8081' } });
  const check = (ok, name) => { if (!ok) throw new Error(name); checks.push(name); };
  await page.route('http://127.0.0.1:8013/**', async route => {
    const req = route.request(); const path = new URL(req.url()).pathname;
    counts[path] = (counts[path] || 0) + 1;
    const body = req.postDataJSON();
    if (path === '/mobile/session') return fulfill(route, { access_token: 'ui-test-only', token_type: 'Bearer', expires_in: 7200 });
    if (path === '/runtime-config') return fulfill(route, { production: true, max_participants: 8, max_candidates: 3, max_k: 3, session_ttl_seconds: 7200, google_available: capacity, google_unavailable_reason: 'Test kotası kapalı.', google_search_capacity: { resolved_coordinates: { 3: { available: capacity, reason: capacity ? '' : 'Test kotası kapalı.' } } } });
    if (path === '/health') return fulfill(route, { status: 'ok', ai_ready: true, ai_provider: 'ollama', ai_model: 'llama3:8b', ai_status: 'ready' });
    if (path === '/locations/parse') return fulfill(route, body.items.map(p => ({ ...p, lat: p.value.includes('hatalı') ? null : 39.92, lng: 32.85, error: p.value.includes('hatalı') ? 'Test: konum çözülemedi.' : null })));
    if (path === '/preferences/interpret') {
      check(!body.participants.some(p => 'value' in p || 'lat' in p), 'LLM request excludes location fields');
      return fulfill(route, { criterion_weights: { rating: 20, cost: 60, proximity: 20 }, participant_proximity_weights: { 'user-1': 2, 'user-2': 1, 'user-3': 1 }, min_rating: null, max_duration_minutes: null, source: 'ollama', model: 'llama3:8b', explanation: 'UI fixture', warnings: [] });
    }
    if (path === '/scenarios') { lastScenario = body; return fulfill(route, scenario); }
    if (path === '/candidates/search') return fulfill(route, candidates);
    if (path === '/routes/matrix') return fulfill(route, partial ? [] : people.flatMap(p => candidates.map(c => ({ user_id: p.id, candidate_id: c.id, duration_seconds: 600, distance_meters: 1500, provider: 'google' }))));
    if (path === '/recommendations') {
      lastRecommendation = body;
      if (recommendFails) return fulfill(route, { detail: 'Test: geçici sunucu hatası.' }, 503);
      return fulfill(route, { scenario, valid_alternatives: 3, criterion_weights: body.criterion_weights, recommendations: body.min_rating > 4.3 ? [] : candidates.map((candidate, i) => ({ rank: i + 1, candidate, score: 0.8 - i / 10, t_avg_minutes: 12, t_max_minutes: 18, directions_url: 'https://www.google.com/maps/dir/?api=1&destination=39.92,32.85&origin=private', cost_source: i ? 'google_price_level' : 'unknown', constraint_status: { complete_route_matrix: true }, per_user: people.map(p => ({ user_id: p.id, label: p.label, raw_duration_minutes: 12, distance_km: 1.5 })), score_breakdown: { rating_component: 0.2, cost_component: 0.3, proximity_component: 0.3, proximity_contributions: people.map(p => ({ user_id: p.id, label: p.label, weight: 1 / 3, distance_km: 1.2 })) } })) });
    }
    if (path === '/mobile/feedback') {
      check(Object.keys(body).sort().join(',') === 'criterion_weights,reason', 'AI report excludes prompt and personal data');
      return fulfill(route, { id: 'test-feedback' }, 201);
    }
    if (path === '/scenarios/test-scenario' && req.method() === 'DELETE') return deleteFails ? fulfill(route, { detail: 'Test: silme tamamlanamadı.' }, 503) : route.fulfill({ status: 204 });
    throw new Error(`Unexpected test endpoint: ${path}`);
  });
  await page.reload();
  await page.getByRole('button', { name: 'Bağlantıyı yenile' }).waitFor();
  await page.getByRole('button', { name: 'Koyu temaya geç' }).click();
  check(await page.getByRole('button', { name: 'Açık temaya geç' }).isVisible(), 'Header theme control switches to dark');
  await page.getByRole('tab', { name: 'Gizlilik', exact: true }).click();
  await page.getByRole('radio', { name: 'Sistem', exact: true }).click();
  check(await page.getByRole('radio', { name: 'Sistem', exact: true }).isChecked(), 'System appearance can be restored');
  await page.getByRole('tab', { name: 'Buluşma', exact: true }).click();
  await page.getByRole('textbox', { name: '1. kişinin konumu', exact: true }).fill('hatalı link');
  await page.getByRole('textbox', { name: '2. kişinin konumu', exact: true }).fill('39.93,32.86');
  await page.getByRole('textbox', { name: '3. kişinin konumu', exact: true }).fill('39.94,32.87');
  await page.getByRole('checkbox', { name: /^Bu kişilerin/ }).click();
  check(await page.getByRole('checkbox', { name: /^Bu kişilerin/ }).isChecked(), 'Consent checked state is accessible');
  await page.getByRole('button', { name: 'Konumları doğrula', exact: true }).click();
  await page.getByText('Test: konum çözülemedi.', { exact: true }).waitFor();
  check(!counts['/scenarios'], 'Invalid location never creates scenario');
  await page.getByRole('textbox', { name: '1. kişinin konumu', exact: true }).fill('https://www.google.com/maps?q=39.92,32.85');
  await page.getByRole('button', { name: 'Konumları doğrula', exact: true }).click();
  await page.getByText('Tüm kişi konumları doğrulandı.').waitFor();
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  check(await page.getByRole('tab', { name: 'Tercihler', exact: true }).getAttribute('aria-selected') === 'true', 'Selected tab state is accessible');
  check(await page.getByRole('radio', { name: 'Dengeli', exact: true }).isChecked(), 'Selected criterion profile state is accessible');
  await page.getByRole('textbox', { name: 'Buluşma tercihiniz' }).fill('Fiyat önemli; Kişi 1 iki kat önemli.');
  await page.getByRole('checkbox', { name: /^Tercih metnimin/ }).click();
  await page.getByRole('button', { name: 'Tercih önerisi oluştur' }).click();
  await page.getByRole('heading', { name: 'Öneriyi incele' }).waitFor();
  check(await page.getByText('Puan %34 · Fiyat %33 · Yakınlık %33', { exact: true }).count() === 1, 'AI preview does not mutate criteria');
  await page.getByRole('button', { name: 'Yapay zekâ önerisini bildir', exact: true }).click();
  await page.getByRole('button', { name: 'Tercihimi yanlış anladı', exact: true }).click();
  await page.getByText(/Bildiriminiz alındı/).waitFor();
  check(counts['/mobile/feedback'] === 1, 'AI report submitted without leaving app');
  await page.getByRole('button', { name: 'Tercih önerisi oluştur' }).click();
  await page.getByRole('heading', { name: 'Öneriyi incele' }).waitFor();
  await page.getByRole('button', { name: 'Bu tercihleri uygula' }).click();
  await page.getByRole('tab', { name: 'Buluşma', exact: true }).click();
  check(await page.getByLabel('Kişi 1 yakınlık ağırlığı: 2×', { exact: true }).count() === 1, 'AI confirmation applies 2/1/1 delta');
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  partial = true;
  await page.getByRole('button', { name: 'Buluşma yeri bul', exact: true }).click();
  await page.getByText(/Bazı rotalar tamamlanamadı/).waitFor();
  check(!counts['/recommendations'], 'Partial matrix never rendered as recommendations');
  partial = false;
  await page.getByRole('button', { name: 'Eksik adımları tamamla', exact: true }).click();
  await page.getByRole('heading', { name: 'Test Kafe 1', exact: true }).waitFor();
  check(counts['/scenarios'] === 1 && counts['/candidates/search'] === 1 && counts['/locations/parse'] === 2, 'Resume reuses scenario, places and validated coordinates');
  check(lastScenario.participant_locations[0].value === '39.92,32.85', 'Scenario uses resolved coordinates not original URL');
  check(lastRecommendation.participant_proximity_weights['user-1'] === 2, 'Recommendation receives person delta');
  check(await page.getByText('Fiyat bilinmiyor; nötr kabul edildi.', { exact: true }).count() > 0, 'Unknown price clearly neutral');
  await page.getByRole('button', { name: 'Neden bu mekân?', exact: true }).first().click();
  await page.getByText('Puan katkısı: 20.0', { exact: true }).first().waitFor();
  const routeCalls = counts['/routes/matrix'];
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  const recalculated = page.waitForResponse(r => r.url().endsWith('/recommendations'));
  await page.getByRole('radio', { name: 'Puan', exact: true }).click();
  await recalculated;
  check(lastRecommendation.criterion_weights.rating === 0.6 && counts['/routes/matrix'] === routeCalls, 'Profile change reranks without route calls');
  await page.getByRole('tab', { name: 'Buluşma', exact: true }).click();
  const balanced = page.waitForResponse(r => r.url().endsWith('/recommendations'));
  await page.getByRole('button', { name: 'Kişiler dengeli', exact: true }).click();
  await balanced;
  check(Object.values(lastRecommendation.participant_proximity_weights).every(n => n === 1), 'Balanced people restores equal weights');
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  await page.getByRole('switch', { name: 'En düşük mekân puanı', exact: true }).click();
  await page.getByRole('button', { name: 'Minimum puan: artır', exact: true }).click();
  await page.getByRole('tab', { name: 'Öneriler', exact: true }).click();
  await page.getByText(/Bu filtrelere uygun mekân bulunamadı/).waitFor();
  checks.push('Empty filter results are explicit');
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  await page.getByRole('switch', { name: 'En düşük mekân puanı', exact: true }).click();
  await page.getByRole('tab', { name: 'Öneriler', exact: true }).click();
  await page.getByRole('heading', { name: 'Test Kafe 1', exact: true }).waitFor();

  for (const [width, height] of [[390, 844], [844, 390], [1024, 1366], [1440, 900]]) {
    await page.setViewportSize({ width, height });
    for (const theme of ['light', 'dark']) {
      await page.emulateMedia({ colorScheme: theme });
      await page.getByRole('heading', { name: 'Test Kafe 1', exact: true }).scrollIntoViewIfNeeded();
      const overflow = await page.evaluate(() => {
        const v = innerWidth;
        return [...document.querySelectorAll('input,button,[role="button"],[role="tab"],[role="heading"]')].filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && (r.left < -1 || r.right > v + 1); }).length;
      });
      check(overflow === 0, `${width}x${height} ${theme} layout no horizontal overflow`);
      await page.screenshot({ path: `output/playwright/mobile-${width}-${theme}.png` });
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'light' });
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  recommendFails = true;
  await page.getByRole('radio', { name: 'Fiyat', exact: true }).click();
  await page.getByText('Test: geçici sunucu hatası.', { exact: true }).waitFor();
  const failedCalls = counts['/recommendations'];
  await page.waitForTimeout(1200);
  check(counts['/recommendations'] === failedCalls, 'Failed recalculation does not loop or auto-retry');
  recommendFails = false;
  await page.getByRole('tab', { name: 'Gizlilik', exact: true }).click();
  deleteFails = true;
  await page.getByRole('button', { name: 'Buluşma verilerimi sil' }).click();
  await page.getByRole('button', { name: 'Verileri sil', exact: true }).click();
  await page.getByText('Test: silme tamamlanamadı.', { exact: true }).waitFor();
  check(await page.getByText('Buluşma verileri temizlendi.').count() === 0, 'Failed deletion is not presented as success');
  deleteFails = false;
  await page.getByRole('button', { name: 'Buluşma verilerimi sil' }).click();
  await page.getByRole('button', { name: 'Verileri sil', exact: true }).click();
  await page.getByText('Buluşma verileri temizlendi.').waitFor();
  check(counts['/scenarios/test-scenario'] === 2, 'Delete reaches server before clearing state');
  await page.getByRole('tab', { name: 'Buluşma', exact: true }).click();
  check(await page.getByRole('textbox', { name: '1. kişinin konumu', exact: true }).inputValue() === '', 'Device location form cleared');
  capacity = false;
  await page.getByRole('button', { name: 'Bağlantıyı yenile', exact: true }).click();
  await page.getByRole('tab', { name: 'Tercihler', exact: true }).click();
  await page.getByText('Test kotası kapalı.', { exact: true }).waitFor();
  check(await page.getByRole('button', { name: 'Buluşma yeri bul', exact: true }).isDisabled(), 'Quota disables new search');
  await page.context().setOffline(true);
  await page.getByText('İnternet bağlantısı yok. Yeni aramalar gönderilmiyor.').waitFor();
  check(await page.getByRole('button', { name: 'Bağlantıyı yenile', exact: true }).isDisabled(), 'Offline state blocks new calls');
  await page.context().setOffline(false);
  await page.getByRole('tab', { name: 'Buluşma', exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('textbox', { name: 'Şehir', exact: true }).waitFor();
  checks.push('Keyboard can navigate tabs');
  await page.unroute('http://127.0.0.1:8013/**');
  await page.reload();
  return { mode: 'mocked UI only, no Google or Llama generation', passed: checks.length, checks, endpointCounts: counts };
}
