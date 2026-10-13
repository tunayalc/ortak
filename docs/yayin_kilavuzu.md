# ORTAK Ücretsiz Yayın Kılavuzu

ORTAK, ücretsiz Oracle Ampere sunucusunda Caddy, FastAPI ve Ollama ile çalışacak kontrollü bir betadır. Bu kılavuz hazırlık, kurulum, test, izleme ve kurtarma adımlarını kapsar. Kodun GitHub'a gönderilmesi, sunucu kabulünün tamamlandığı anlamına gelmez.

## Ücretsiz kaynak ve erişim

Ana bölge Frankfurt olacak. Yalnızca konsolda Always Free uygunluğu ve hesap genelindeki kullanılabilir kotası doğrulanan 2 OCPU, 12 GB bellek, 50 GB boot disk kullanılacak. Ücretli yükseltme, yük dengeleyici, NAT Gateway veya alan adı alınmayacak. Kapasite yetersizliğinde oluşturma en sık saatte bir denenecek. [Oracle sınırları](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

Ubuntu ARM64 sunucusunda SSH yalnızca yönetici IP'sine `/32` ile açılır. HTTP 80 ve HTTPS 443 uygulama yayını için kullanılır; FastAPI 8000 ve Ollama 11434 dışarıya açılmaz. Oracle güvenlik listesi ve sunucu güvenlik duvarı birlikte doğrulanır. Parola ve banka doğrulamalarını kullanıcı tamamlar; yeni sözleşme veya erişim yetkileri ilgili aşamada onaylanır.

## Üretim kurulumu

Testleri geçen commit `/opt/ortak` içine alınır. Docker ve Compose resmî Docker kaynağından kurulur. `deploy/.env.example` üretim için örnektir; gerçek `.env` özel kalır ve `0600` izinle tutulur. Alan adı sunucu IP'sinin `nip.io` karşılığıdır. API ve web imajları başarılı GitHub Actions işinin ARM64 digest değerleriyle sabitlenir. İmajların sunucudan erişilebilirliği doğrulanır; paket görünürlüğü doğrulanmadan dağıtım hazır sayılmaz.

```bash
cd /opt/ortak/deploy
sudo install -d -m 700 -o 10001 -g 10001 data guard backups
install -d -m 700 private
python3 operations.py verify
```

`SESSION_SECRET` en az 32 rastgele karakter olmalı; örnek yer tutucular kabul edilmez. Caddy güvenilir vekil adresi `172.30.0.2` olarak sabittir. Başka ağdan gelen `X-Forwarded-For` başlıkları API tarafından güvenilir kabul edilmez. Compose ağı bu subnet ile çakışırsa API vekil adresi ve Compose birlikte değiştirilip yeniden test edilir.

## Google kullanım kaydını taşıma

Önce yerelde ücretli çağrılar kapatılır ve çalışan backend'in yeniden yüklediği doğrulanır. Eski SQLite dosyasını sunucuya kopyalamayın: sentetik senaryo veya eski Google içeriği barındırabilir. Yalnızca `google_api_usage` kayıtları aktarılır; deneme sayıları sıfırlanmaz.

```bash
cd backend
.venv-release/bin/python scripts/backup_database.py export-ledger ../output/deployment/ledger.json
```

Özel dosya güvenilir SSH üzerinden sunucunun `deploy/private/` dizinine aktarılır. API başlatılmadan önce Compose tek seferlik konteynerinde ledger içeri alınır:

```bash
docker compose run --rm --no-deps -v "$(pwd)/private:/transfer:ro" api python scripts/backup_database.py import-ledger /transfer/ledger.json
```

Bu komut için `deploy/private` geçici olarak `/transfer:ro` bağlanır; aktarım kaydı uygulama imajına eklenmez. Kullanım geçmişi gerçekten yoksa `initialize-empty-ledger` yalnızca ilk kurulumda kullanılabilir. Mevcut guard veya kullanım kaydı varken yeniden başlatma olarak kullanılamaz. Guard ayrı dizinde tutulur; veritabanı kaybolur veya eski yedeğe dönerse Google çağrıları kapanır. Guard kaybolursa otomatik yeniden oluşturulmaz; eski kayıtlar ve Cloud Billing uzlaştırılır.

Anahtar yalnızca üç Google API'sine ve sunucunun çıkış IP'sine sınırlandırılır. Yereldeki ücretli çağrılar kapalı kalır. Normal sağlık kontrolü Google'a istek göndermez. Genel günlük 33 deneme yanında Geocoding toplam 3, Nearby Search 3, Routes 27 sınırı backend'de de uygulanır. Başarısız ve yeniden denenen istekler de sayılır.

Google başlangıçta kapalıdır. Pilot için vergi ve kur dâhil ihtiyatlı birim TL fiyatları, kaynakları ve doğrulama zamanı girilir. Fiyat bilgisi eksik veya yedi günden eskiyse çağrılar durur. İlk pilot bütçesi en fazla 100 TL'dir; ileride ayrıca onaylanmış kullanım bile 1.200 TL güvenlik rezervini aşamaz. Ön ödeme, kullanım hedefi ve kesin tahsilat tavanı değildir. [Google fiyatları](https://developers.google.com/maps/billing-and-pricing/pricing)

## Başlatma ve kabul

```bash
python3 operations.py apply
docker compose exec ollama ollama pull llama3:8b
docker compose exec api python scripts/evaluate_preferences.py --repeats 3 --output /backups/llama-acceptance.json
```

Model indirme bir kez yapılır; başka modele veya buluta otomatik geçiş yoktur. Sunucuda 36/36 kontrol, her istekte en fazla 120 saniye ve bellek taşması olmaması gerekir. Model mevcut diye anlamsal doğruluk kabul edilmez. Manuel kontroller model kesintisinde kullanılabilir.

Google pilotundan önce kullanıcıya maliyet tahmini sunulur ve tek onay alınır. Günlük ve servis kotaları yeniden denemeler için yeterli olmalı; yetersizse sonraki gün beklenir. Tam üç kişi × üç aday rota matrisi, Google kaynağı ve kriter katkıları doğrulanır. Profil değişikliği yeni rota çağrısı yapmamalıdır. Test bittikten sonra Google yeniden kapatılır; genel kullanıma açma ayrı bütçe kapsamıyla yapılır.

```bash
cd backend
.venv-release/bin/python scripts/evaluate_google_maps.py --api-base https://SERVER_IP.nip.io/api/ --live --max-spend-tl 100
```

Bu komut bütçeyi kendi başına etkinleştirmez; sunucu rezervasyonu ve ayrıca alınmış harcama onayı gerekir. Eksik matris veya sentetik yanıt canlı Google başarısı sayılmaz. HTTP ön kontrol hataları da başarısız kayıt olarak saklanır.

## İzleme ve yedekleme

```bash
sudo install -m 644 systemd/ortak-*.service systemd/ortak-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ortak-health.timer ortak-backup.timer
```

Sağlık kontrolü beş dakikada bir HTTPS, SQLite, model listesi, disk ve konteyner durumunu okur; ücretli Google çağrısı veya model üretimi yapmaz. Ham tercih, konum, IP, model yanıtı ve sorgu parametreleri günlüğe yazılmaz. 24 saatlik gözlemde başarısız kontrol veya on dakikayı aşan boşluk gözlem süresini yeniden başlatır. API çökünce oturumluk konumlar kaybolur.

SQLite backup API'siyle günlük tutarlı yedek alınır; son yedi kopya özel tutulur. Sağlık kayıtları `deploy/private/` altındadır. Bunlar GitHub'a gönderilmez. Yerel Codex takibi için bilgisayar ve uygulama açık olmalıdır; sunucu timer'ları bundan bağımsızdır. [Codex otomasyonları](https://learn.chatgpt.com/docs/automations?surface=app)

## Geri dönüş ve kurtarma

Google çağrılarını kapattıktan sonra `python3 operations.py rollback` önceki imajlara döner; veri, guard, model ve sertifika dizinlerine dokunmaz. Eski SQLite dosyasını çalışan veritabanının üzerine yazmak yasaktır. Felaket kurtarmada API durdurulur, özel yedek ayrı konuma doğrulanır ve en güncel ledger ile birleştirilir. Kaybolmuş kullanımı doğrulamak mümkün değilse Google kapalı kalır. Guard'ı silmek veya sayacı düşürmek kurtarma yöntemi değildir.

## Tamamlanma ölçütü

GitHub deposu, ARM64 imajlar, sunucuda Llama kabulü, onaylı Google pilotu, dış istemciden HTTPS ve öneri doğrulaması, yedekten kurtarma ve kesintisiz 24 saatlik sağlık gözlemi birlikte tamamlanmalıdır. Son teslimde sürüm etiketi, temizlenmiş sonuç özeti ve tamamlandı–eksik–engelli listesi verilir. Yayın takip otomasyonu yalnızca bu teslimden sonra duraklatılır. Ücretsiz kaynakların kesintisiz çalışması garanti değildir; yapay yük üreterek Oracle'ın boşta kalma kuralları aşılmaz.
