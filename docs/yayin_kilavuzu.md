# ORTAK Ücretsiz Yayın Kılavuzu

ORTAK, ücretsiz Oracle Ampere sunucusunda Caddy, FastAPI ve Ollama ile çalışacak kontrollü bir betadır. Bu kılavuz hazırlık, kurulum, test, izleme ve kurtarma adımlarını kapsar. Kodun GitHub'a gönderilmesi, sunucu kabulünün tamamlandığı anlamına gelmez.

## 13 Ekim 2026 Durumu

| Kontrol | Durum |
| --- | --- |
| Backend testleri | 142/142 başarılı; yerel pilot bütçe koruması, model ön kontrolü, özel ledger aktarımı, kullanım guard'ının paylaşım dışı tutulması ve konteynerde pilot CLI açılışı doğrulandı |
| Mobil ve masaüstü arayüz testleri | 26/26 başarılı; 390 ve 1440 piksel, açık/koyu tema; onaylı tercih ile konum araması da sınandı |
| Gerçek yerel Llama 3 8B | 36/36 başarılı; ortalama 2,10 sn, azami 6,87 sn; Oracle performansı değildir |
| Yerel ARM64 API ve web imajları | Güncel API ve web imajları derlendi; üretim açılışı, bütçe koruması, pilot CLI, Caddy, `/api` bağlantısı ve özel dosya yokluğu doğrulandı. GitHub Actions / GHCR kabulü bekliyor; yerel kontrol canlı yayın değildir |
| Tutarlı SQLite yedeği | Birim testlerinde ve ARM64 konteynerinde doğrulandı |
| GitHub deposu | Oluşturuldu; kod gönderimi eksik workflow yetkisi nedeniyle bekliyor |
| Oracle hesabı ve ücretsiz kapasite | Frankfurt hesabı doğrulandı; kullanıcı tarafından gönderilen AD-3 oluşturma denemesi kapasite hatasıyla durdu. Sunucu, VCN, blok ve boot disk listelerinde kaynak görülmedi. SSH açık anahtarı doğrulandı; sonraki deneme için AD-1, 2 OCPU / 12 GB RAM ve 50 GB disk hazırlandı. Canlı sunucu yok |
| Sunucuda Llama, Google pilotu, HTTPS ve 24 saat gözlem | Bekliyor; tamamlandı sayılmıyor |

Bu turda yeni ücretli Google Maps API çağrısı, ücretli sunucu veya ödeme işlemi yapılmadı. Gerçek Llama testi yalnızca kurgusal geliştirme cümleleriyle yapıldı; genel doğruluk iddiası değildir. Sonraki kontrol sonuçları bu tabloya kanıtlarıyla eklenir.

## Ayrı Yerel Google Pilotu

Kullanıcı, mevcut Ollama `llama3:8b` modeliyle yalnızca Google Maps için en fazla 100 TL kapsamını seçti ve aşağıdaki maliyet tahminiyle tek yerel pilotu onayladı; ücretli model barındırma seçilmedi. Yeni ücretli istek henüz gönderilmedi. Pilot, yeterli kota ve model bağlantısı doğrulanana kadar bekler. Bu izin GitHub erişimini genişletmez ve yerel sonucu Oracle sunucu kabulü yapmaz.

13 Ekim'de doğrulanan [Google fiyatları](https://developers.google.com/maps/billing-and-pricing/pricing): Geocoding 0,005 USD, Nearby Search Enterprise 0,035 USD, trafik verili Compute Routes Pro 0,010 USD/istek. Üç kurgusal kişi ve üç aday için 11 normal çağrı 0,13 USD, tüm istekler iki kez yeniden denenirse 33 deneme 0,39 USD eder. [Google Türkiye KDV oranı %20'dir](https://docs.cloud.google.com/billing/docs/resources/vat-overview). [TCMB'nin son yayımlanan bülteni](https://www.tcmb.gov.tr/kurlar/today.xml), 12 Ekim için USD döviz satışını 49,3358 TL gösterdi. Bu TCMB değeri Google'ın fatura kuru değildir.

İhtiyatlı rezervasyonda 60 TL/USD ve ayrıca %25 güvenlik payı kullanıldı: normal 11,70 TL, azami 35,10 TL. Ücretsiz kullanım düşülmedi; gerçek fatura daha düşük veya sıfır olabilir. Rezervasyon banka tahsilatı için kesin tavan değildir. Kaynaklı özel fiyat kaydı ve ön kontrol sonucu GitHub dışında tutulur; çalıştırmadan önce fiyat, kur, vergi ve servis kotaları yeniden doğrulanır.

13 Ekim'de backend'de 22 deneme hakkı kaldı. [Geocoding günlük kotası Pasifik gece yarısında yenilenir](https://developers.google.com/maps/documentation/geocoding/usage-and-billing); sonraki kontrol en erken 14 Ekim 10.00 İstanbul saatidir. Sayaçlar sıfırlanmaz ve kota artırılmaz.

Onaylanan yerel pilot ayrı ve yalnızca `127.0.0.1` üzerinde erişilen geçici backend'de çalıştırılır. Ana uygulamadaki ücretli çağrılar kapalı kalır. Mevcut veritabanı ve guard dosyasının mutlak yolları doğrulanıp aynı kullanım kaydı kullanılır; yeni bir boş veritabanıyla kotayı yeniden başlatmak yasaktır. Geçici backend için `GOOGLE_BUDGET_ENFORCEMENT_ENABLED=true`, `GOOGLE_BUDGET_LIMIT_TL=100`, doğrulanmış birim TL rezervleri ve fiyat kaynakları zorunludur. Bu ayarlar örnek dosyada bulunur; gerçek anahtar paylaşılmaz. Bütçe koruması, fiyat veya guard eksikse test Google'a istek göndermez.

```bash
cd backend
.venv-release/bin/python scripts/evaluate_google_maps.py --api-base http://127.0.0.1:8012 --live --with-llama --max-spend-tl 100
```

Bu komut yalnızca son onay, yeterli kota ve korumalı geçici backend hazırken çalıştırılır. Önce mevcut gerçek Llama'nın puan/fiyat/yakınlık ve `2x/1x/1x` tercihi doğrulanır; sonra Google matrisi kurulur ve öneriye uygulanır. Model hazır değilse veya yanlış tercih döndürürse ücretli mekân araması başlamaz. Profil ve kişi tercihi değişikliklerinin ek Google çağrısı üretmemesi ayrıca kontrol edilir. Model kaynağı, süreler, çağrı sayıları, ağırlıklar ve kontrol sonuçları kaydedilir; ham tercih, koordinat ve Google içerikleri kaydedilmez. Oracle'daki Google pilotu bu yerel çalışmanın devamı olarak otomatik yeniden yapılmaz; sunucu üzerinde ücretli tekrar ayrı onay gerektirir.

## Tercihten konuma dayalı aramaya geçiş

Modelin önerdiği kriter ve kişi ağırlıkları önce düzenlenebilir önizlemede gösterilir. “Uygula ve mekânları bul” onayı, kişi konumu alanlarıyla birlikte öneri akışını başlatır. Model konum bağlantılarını veya koordinatları almaz; yalnızca anonim kişi kimlikleri ve seçim tercihiyle çalışır. Mekân bulma, rota ve sıralama işlemlerini doğrulanmış uygulama kodu yürütür.

Konumlar ve arama alanları değişmemişse tamamlanmış rota matrisi yeniden kullanılır. Yalnızca kriter veya kişi ağırlığı değişikliği yeni Google isteği üretmez. Konum, şehir veya kategori değişirse eski öneriler kaldırılır; yeni arama kullanıcı onayı gerektirir. Arama sürerken konum değişirse sonraki aşamalar durdurulur ve eski sonuç güncelmiş gibi gösterilmez. Üretimde Google kullanımı kapalıysa yeni arama engellenir; manuel tercih düzenleme kullanılabilir.

Bu akışın arayüz testleri kurgusal model önerileri ve Google kullanılmayan test backend'iyle çalışır. İnternet üzerinden erişilebilir Llama, gerçek Google ve sunucu kabulü yerine geçmez. Kullanıcının ücretli deneme talebinde Google Maps kullanımı ile Google Cloud'da Llama barındırma ayrı maliyet kalemleridir. Kapsam, güncel fiyat ve bütçe netleşmeden ücretli sunucu veya yeni Google pilotu başlatılmaz; önceki 100 TL pilot sınırı artırılmaz.

## Ücretsiz kaynak ve erişim

Ana bölge Frankfurt olacak. Yalnızca konsolda Always Free uygunluğu ve hesap genelindeki kullanılabilir kotası doğrulanan 2 OCPU, 12 GB bellek, 50 GB boot disk kullanılacak. Ücretli yükseltme, yük dengeleyici, NAT Gateway veya alan adı alınmayacak. Kapasite yetersizliğinde oluşturma en sık saatte bir denenecek. [Oracle sınırları](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

13 Ekim'de yetkili konsolda Frankfurt ana bölgesi ve Free Tier hesap doğrulandı. Bölgesel Ampere işlemci ve bellek kullanımı sıfır, ücretsiz boot/blok disk kotası 200 GB ve kullanım sıfır görüldü. Deneme hesabının daha geniş servis limiti ücretsiz kullanım izni değildir. Resmî Always Free belgesindeki aylık 1.500 OCPU-saat ve 9.000 GB-saat sınırları korunur. `VM.Standard.A1.Flex` için 2 OCPU ve 12 GB, ücretsiz `Canonical Ubuntu 24.04 Minimal aarch64` imajı formda seçildi. İlk hazırlık aşamasında ajan oluşturma isteği göndermedi; ardından kullanıcının gönderdiği deneme aşağıdaki kapasite hatasıyla sonuçlandı. Formun açılması fiziksel sunucu kapasitesi bulunduğunu kanıtlamaz.

Dağıtım için ayrı bir SSH anahtarı özel dizinde üretildi; yalnızca açık anahtar Oracle'a verilebilir. Kullanıcının yapıştırdığı açık anahtar, yereldeki anahtarın SHA-256 özetiyle karşılaştırılarak doğrulandı. Özel anahtar gönderilmedi ve yeni tarayıcı dosya erişim yetkisi açılmadı. Aynı SSH anahtarı yeniden kullanılmalı; anahtar üretimi otomatik tekrarlanmamalı.

Kullanıcı tarafından gönderilen AD-3 oluşturma isteği kapasite hatasıyla durdu. Frankfurt kök bölmesindeki sunucu, VCN, blok disk ve boot disk listelerinde kaynak görülmedi. Sonraki deneme için AD-1 seçildi; 2 OCPU, 12 GB bellek, ücretsiz Ubuntu ARM64 imajı, 50 GB boot disk ve 10 VPU dengeli disk performansı formda doğrulandı. Bu hazırlık yeni oluşturma isteği veya fiziksel kapasite kanıtı değildir. Sabit fault domain seçilmedi. Genel IP ve IPv6 ilk oluşturma sırasında kapalı tutulacak; ağ güvenlik kuralları doğrulanmadan dış erişim açılmayacak.

Maliyet penceresinde boot disk için aylık 1,98 EUR liste tahmini görüldü; pencere hesap kotasının ücretsiz tahsisini doğrulayan bir fatura değildir. [Resmî Always Free kapsamı](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), ana bölgede toplam 200 GB boot/blok disk ve aylık 1.500 OCPU-saat / 9.000 GB-saat içerir. Her gerçek oluşturma isteğinden önce hesap genelindeki boş kota ve ücretsiz uygunluk yeniden kontrol edilir. Uygunluk belirsizse oluşturma yapılmaz; deneme kredileri ücretli kaynak açma izni değildir.

Son oluşturma zamanının kesin bilinmediği durumda bir saatlik bekleme, hata gözlemi üzerinden ihtiyatlı hesaplanır. Özel durum kaydı, aynı denemenin otomasyon tarafından hemen tekrarlanmasını engeller. Yeniden denemeden önce mevcut kaynaklar tekrar uzlaştırılır; başarısız isteğin bıraktığı kaynak varsa yeni bir kopya oluşturulmaz. Kapasite beklerken ücretli şekle veya ücretli hesap yükseltmesine geçilmez.

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

Özel dosya güvenilir SSH üzerinden sunucunun `deploy/private/` dizinine aktarılır. Dizin yöneticiye ait ve `0700`, kaynak dosya `0600` kalır. API başlatılmadan önce ledger içeri alınır:

```bash
sudo python3 operations.py import-ledger --ledger private/ledger.json
```

Bu komut yalnızca ledger kopyasını içeren geçici bir dizini API'nin `10001` kullanıcısına verir ve `/transfer:ro` olarak bağlar. Özel dizinin tamamı, sağlık kayıtları veya sürüm dosyaları API'ye açılmaz. Başarıda ve hatada geçici kopya kaldırılır; asıl aktarım dosyası saklanır. Aktarım kaydı uygulama imajına eklenmez ve Google çağrıları açılmaz. Kullanım geçmişi gerçekten yoksa `initialize-empty-ledger` yalnızca ilk kurulumda kullanılabilir. Mevcut guard veya kullanım kaydı varken yeniden başlatma olarak kullanılamaz. Guard ayrı dizinde tutulur; veritabanı kaybolur veya eski yedeğe dönerse Google çağrıları kapanır. Guard kaybolursa otomatik yeniden oluşturulmaz; eski kayıtlar ve Cloud Billing uzlaştırılır.

Anahtar yalnızca üç Google API'sine ve sunucunun çıkış IP'sine sınırlandırılır. Ana yerel uygulamadaki ücretli çağrılar kapalı kalır; tek onaylı yerel pilot yalnızca yukarıdaki ayrı, korumalı süreçte çalışabilir. Normal sağlık kontrolü Google'a istek göndermez. Genel günlük 33 deneme yanında Geocoding toplam 3, Nearby Search 3, Routes 27 sınırı backend'de de uygulanır. Başarısız ve yeniden denenen istekler de sayılır.

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
