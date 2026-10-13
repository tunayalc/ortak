# ORTAK Ücretsiz Yayın Kılavuzu

ORTAK, ücretsiz Oracle Ampere sunucusunda Caddy, FastAPI ve Ollama ile çalışacak kontrollü bir betadır. Bu kılavuz hazırlık, kurulum, test, izleme ve kurtarma adımlarını kapsar. Kodun GitHub'a gönderilmesi, sunucu kabulünün tamamlandığı anlamına gelmez.

## 14 Ekim 2026 Durumu

| Kontrol | Durum |
| --- | --- |
| Backend testleri | 152/152 başarılı; kullanım kaydı birleştirme ve servis bazlı kota kontrolü de test edildi |
| Mobil ve masaüstü arayüz testleri | 26/26 başarılı; 390 ve 1440 piksel, açık/koyu tema; onaylı tercih ile konum araması da sınandı |
| Gerçek yerel Llama 3 8B | 36/36 başarılı; ortalama 2,10 sn, azami 6,87 sn; Oracle performansı değildir |
| GitHub Actions ve ARM64 imajları | [İş akışı 38468540861](https://github.com/tunayalc/ortak/actions/runs/38468540861) başarılı: test, API ve web ARM64 imaj işleri geçti |
| Tutarlı SQLite yedeği | Birim testlerinde ve ARM64 konteynerinde doğrulandı |
| GitHub deposu | [tunayalc/ortak](https://github.com/tunayalc/ortak) açık; yeni sunucuda `cfa3026` commit'i çalışıyor |
| Oracle hesabı ve ücretsiz kapasite | Frankfurt AD-1'deki eski `ortak-beta` ve 50 GB boot diski sonlandırıldı. Yalnızca `ortak-beta-yeni` 2 OCPU/12 GB ve yaklaşık 47 GB boot diskiyle çalışıyor. Kısa süreli sunucu örtüşmesinin deneme kredisi kullanımına etkisi fatura ekranından ayrıca kontrol edilmeli |
| Dış HTTPS | [Yeni sunucu](https://92.5.80.85.nip.io/) ve `/api/health` dışarıdan HTTPS 200 döndü; sertifika doğrulaması başarılı. On eşzamanlı `/api/readyz` isteği 200 döndü; API ve Ollama portları dışarıdan erişilemedi |
| Sunucuda Llama 3 8B | İlk soğuk deney 35/36 idi: ilk istek 120,136 saniye. Başarısız rapor ayrı saklandı. Açılış yüklemesinden sonraki gerçek deney 36/36 geçti; en yavaş yanıt 51,756 saniye ve üç konteynerde OOM yok |
| Canlı tarayıcıda Llama önizlemesi | “Mekân puanı daha önemli olsun, kişiler dengeli kalsın” isteği 70/33/33 kriter ve 1/1/1 kişi ağırlığı önerdi. Önizleme uygulanmadan kapatıldı; Google çağrısı yapılmadı |
| Sağlık ve yedek | Model açılış servisi ile sağlık/yedek zamanlayıcıları etkin. Sağlık kontrolü geçti; ayrı SQLite yedeğinde bütünlük ve 11 satırlık kullanım kaydının guard ile eşleşmesi doğrulandı |
| Google ve 24 saat gözlem | Yerel, korumalı pilot gerçek Google ile geçti: 1 Geocoding, 1 Places, 9 Routes; üç kişi ve üç aday için rota matrisi tam. Oracle'da yalnızca `92.5.80.85/32` ve üç API ile sınırlandırılmış ayrı anahtar kuruldu; çağrılar hâlâ kapalı. Sunucu pilotu, genel öneri akışı ve 24 saatlik gözlem tamamlanmadı |

14 Ekim'de kullanıcı, önceki 10.00 bekleme koşulunu açıkça değiştirerek yerel pilotun hemen başlatılmasını istedi. Onaylı 100 TL sınırıyla 11 gerçek Google isteği yapıldı; yeniden deneme olmadı. Bu, genel doğruluk veya Google faturası hakkında kesin bir iddia değildir. Ücretli sunucu, ödeme işlemi veya ikinci Google pilotu başlatılmadı.

## Ayrı Yerel Google Pilotu

Kullanıcı, mevcut Ollama `llama3:8b` modeliyle yalnızca Google Maps için en fazla 100 TL kapsamını seçti ve aşağıdaki maliyet tahminiyle tek yerel pilotu onayladı; ücretli model barındırma seçilmedi. Yerel pilot 14 Ekim'de tamamlandı. Kullanıcı, bunun ardından Oracle'da ayrı ve yine en fazla 100 TL'lik ikinci bir pilotu da onayladı; bu ikinci pilot henüz çalıştırılmadı. Yerel sonuç Oracle sunucu kabulü değildir.

14 Ekim çalışması öncesinde yeniden doğrulanan [Google fiyatları](https://developers.google.com/maps/billing-and-pricing/pricing): Geocoding 0,005 USD, Nearby Search Enterprise 0,035 USD, trafik verili Compute Routes Pro 0,010 USD/istek. Üç kurgusal kişi ve üç aday için 11 normal çağrı 0,13 USD, tüm istekler iki kez yeniden denenirse 33 deneme 0,39 USD eder. [Google Türkiye KDV oranı %20'dir](https://docs.cloud.google.com/billing/docs/resources/vat-overview). [TCMB'nin 13 Ekim bülteni](https://www.tcmb.gov.tr/kurlar/today.xml) USD döviz satışını 49,3681 TL gösterdi. Bu TCMB değeri Google'ın fatura kuru değildir.

İhtiyatlı rezervasyonda 60 TL/USD ve ayrıca %25 güvenlik payı kullanıldı: normal 11,70 TL, azami 35,10 TL. Ücretsiz kullanım düşülmedi; gerçek fatura daha düşük veya sıfır olabilir. Rezervasyon banka tahsilatı için kesin tavan değildir. Kaynaklı özel fiyat kaydı ve ön kontrol sonucu GitHub dışında tutulur; çalıştırmadan önce fiyat, kur, vergi ve servis kotaları yeniden doğrulanır.

Yerel pilot öncesi backend'de 33 deneme, Google konsolunda Geocoding 3, Places 3, Routes 27 günlük hak vardı. Pilot sonrası mevcut gün için yerel kalan haklar 22 ve servis bazında 2/2/18 oldu. [Google günlük kotası Pasifik gece yarısında yenilenir](https://developers.google.com/maps/documentation/geocoding/usage-and-billing); ikinci pilot için Google kotaları ile taşınmış backend sayacı birlikte yeniden doğrulanır. Sayaçlar sıfırlanmaz ve kota artırılmaz.

Onaylanan yerel pilot ayrı ve yalnızca `127.0.0.1` üzerinde erişilen geçici backend'de çalıştırılır. Ana uygulamadaki ücretli çağrılar kapalı kalır. Mevcut veritabanı ve guard dosyasının mutlak yolları doğrulanıp aynı kullanım kaydı kullanılır; yeni bir boş veritabanıyla kotayı yeniden başlatmak yasaktır. Geçici backend için `GOOGLE_BUDGET_ENFORCEMENT_ENABLED=true`, `GOOGLE_BUDGET_LIMIT_TL=100`, doğrulanmış birim TL rezervleri ve fiyat kaynakları zorunludur. Bu ayarlar örnek dosyada bulunur; gerçek anahtar paylaşılmaz. Bütçe koruması, fiyat veya guard eksikse test Google'a istek göndermez.

```bash
cd backend
.venv-release/bin/python scripts/evaluate_google_maps.py --api-base http://127.0.0.1:8012 --live --with-llama --max-spend-tl 100
```

Bu komut yalnızca son onay, yeterli kota ve korumalı geçici backend hazırken çalıştırılır. 14 Ekim pilotunda gerçek Llama'nın `2x/1x/1x` kişi ve puan/fiyat/yakınlık tercihi Google aramasından önce doğrulandı. Üç kişi x üç aday için tam dokuz Google rotası alındı. Profil ve kişi tercihi değişiklikleri ek çağrı üretmedi; 13/13 kontrol geçti. Test raporu GitHub dışındaki `output/google_maps/local-approved-20261014-early/` dizinindedir. Ham tercih, koordinat ve Google içerikleri kaydedilmez. Toplam kullanım kaydı 22 satırdır ve guard ile eşleşir; 46,35 TL tüm kayıtlar için ayrılmış ihtiyatlı maliyettir, fatura tutarı değildir. Oracle pilotu ayrı onaylanmıştır ancak servis kotası ve ortak kullanım kaydı yeterli olmadan başlatılmaz.

## Tercihten konuma dayalı aramaya geçiş

Modelin önerdiği kriter ve kişi ağırlıkları önce düzenlenebilir önizlemede gösterilir. “Uygula ve mekânları bul” onayı, kişi konumu alanlarıyla birlikte öneri akışını başlatır. Model konum bağlantılarını veya koordinatları almaz; yalnızca anonim kişi kimlikleri ve seçim tercihiyle çalışır. Mekân bulma, rota ve sıralama işlemlerini doğrulanmış uygulama kodu yürütür.

Konumlar ve arama alanları değişmemişse tamamlanmış rota matrisi yeniden kullanılır. Yalnızca kriter veya kişi ağırlığı değişikliği yeni Google isteği üretmez. Konum, şehir veya kategori değişirse eski öneriler kaldırılır; yeni arama kullanıcı onayı gerektirir. Arama sürerken konum değişirse sonraki aşamalar durdurulur ve eski sonuç güncelmiş gibi gösterilmez. Üretimde Google kullanımı kapalıysa yeni arama engellenir; manuel tercih düzenleme kullanılabilir.

Bu akışın arayüz testleri kurgusal model önerileri ve Google kullanılmayan test backend'iyle çalışır. İnternet üzerinden erişilebilir Llama, gerçek Google ve sunucu kabulü yerine geçmez. Kullanıcının ücretli deneme talebinde Google Maps kullanımı ile Google Cloud'da Llama barındırma ayrı maliyet kalemleridir. Kapsam, güncel fiyat ve bütçe netleşmeden ücretli sunucu veya yeni Google pilotu başlatılmaz; önceki 100 TL pilot sınırı artırılmaz.

## Ücretsiz kaynak ve erişim

Ana bölge Frankfurt olacak. Yalnızca konsolda Always Free uygunluğu ve hesap genelindeki kullanılabilir kotası doğrulanan 2 OCPU, 12 GB bellek, 50 GB boot disk kullanılacak. Ücretli yükseltme, yük dengeleyici, NAT Gateway veya alan adı alınmayacak. Kapasite yetersizliğinde oluşturma en sık saatte bir denenecek. [Oracle sınırları](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

13 Ekim'de yetkili konsolda Frankfurt ana bölgesi ve Free Tier hesap doğrulandı. İlk AD-3 denemesi kapasite hatası verdi. Daha sonra kullanıcı, AD-1'de `VM.Standard.A1.Flex` (2 OCPU, 12 GB) ve `Canonical Ubuntu 24.04 Minimal aarch64` ile `ortak-beta` sunucusunu oluşturdu. İlk kontrol anında CPU/bellek kullanımı 2/12, bölgesel ücretsiz boot/blok disk kotası 200 GB içinden kullanım 50 GB idi. Daha sonra yeni sunucu kurulmasıyla toplam boot disk kullanımı yaklaşık 97 GB oldu. Deneme hesabının daha geniş servis limiti ücretsiz kullanım izni değildir. Resmî Always Free belgesindeki aylık 1.500 OCPU-saat ve 9.000 GB-saat sınırları korunur.

Dağıtım için ayrı bir SSH anahtarı özel dizinde üretildi; yalnızca açık anahtar Oracle'a verilebilir. Kullanıcının yapıştırdığı açık anahtar, yereldeki anahtarın SHA-256 özetiyle karşılaştırılarak doğrulandı. Özel anahtar gönderilmedi ve yeni tarayıcı dosya erişim yetkisi açılmadı. Aynı SSH anahtarı yeniden kullanılmalı; anahtar üretimi otomatik tekrarlanmamalı.

İlk AD-3 kapasite hatasından sonra AD-1'de `ortak-beta` kurulmuştu. Sunucu içindeki eski yönetici IP kuralı nedeniyle SSH erişimi kesilince ve onarım yolu sonuç vermeyince kullanıcı talebiyle aynı bölgede `ortak-beta-yeni` oluşturuldu. Resmî ücretsiz A1 tahsisi iki makineye ayrı ayrı değil, hesap genelinde toplam 2 OCPU/12 GB'dır; bu nedenle eski makine durdurulup veri kontrolünden sonra sonlandırıldı. `ortak-vcn` içindeki alt ağ genel alt ağdır; internet ağ geçidi ve `0.0.0.0/0` yönlendirmesi vardır. Yeni makinenin SSH kuralı yalnızca güncel yönetici `/32` adresine, TCP 80/443 web erişimine açıktır; 8000 ve 11434 dışarı açılmadı.

Eski boot diski yeni sunucuya salt okunur veri diski olarak bağlandı. Eski ve yeni veritabanlarında senaryo, aday, rota ve öneri koşusu yok; 11 Google kullanım kaydı ve guard eşleşiyor. Eski yapılandırmada Google anahtarı bulunmadı; ev dizininde ayrıca taşınması gereken kullanıcı dosyası görülmedi. Geçici disk eki `DETACHED` olarak doğrulandı. Kullanıcının kalıcı silme onayından sonra eski VM ve 50 GB boot diski Oracle'da `Terminated` durumuna geçti; yeni sunucuda ikinci disk yok. [Oracle belgeleri](https://docs.oracle.com/en-us/iaas/Content/Block/Tasks/attach-compute-boot-volume-attachment.htm), durmuş örneğin boot diskinin başka bir örneğe veri diski olarak bağlanabildiğini açıklıyor.

Maliyet penceresinde boot disk için aylık 1,98 EUR liste tahmini görüldü; pencere hesap kotasının ücretsiz tahsisini doğrulayan bir fatura değildir. [Resmî Always Free kapsamı](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), ana bölgede toplam 200 GB boot/blok disk ve aylık 1.500 OCPU-saat / 9.000 GB-saat içerir. Her gerçek oluşturma isteğinden önce hesap genelindeki boş kota ve ücretsiz uygunluk yeniden kontrol edilir. Uygunluk belirsizse oluşturma yapılmaz; deneme kredileri ücretli kaynak açma izni değildir.

Özel durum kaydı, mevcut kaynağın kimliğini ve ücretsiz kota kullanımını tutar. Önceki kapasite hatası yeni deneme nedeni sayılmaz; mevcut sunucu kullanılır. Ücretli şekle veya ücretli hesap yükseltmesine geçilmez.

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

Özel dosya güvenilir SSH üzerinden sunucunun `deploy/private/` dizinine aktarılır. Dizin yöneticiye ait ve `0700`, kaynak dosya `0600` kalır. Google çağrıları kapalıyken ve API konteyneri çalışırken ledger içeri alınır:

```bash
sudo python3 operations.py import-ledger --ledger private/ledger.json
```

Bu komut özel kaynağın yalnızca geçici kopyasını, erişimi `10001` kullanıcısıyla sınırlı `/backups` dizinine koyar ve çalışan API konteynerinde içe alır. Ayrı konteyner veya çakışan statik IP oluşturulmaz. Başarıda ve hatada geçici kopya kaldırılır; asıl aktarım dosyası saklanır. Eski kayıtlardaki boş maliyet rezervi yalnızca diğer tüm alanlar eşitse ve yeni değer pozitifse tamamlanır; başka çakışma tüm işlemi durdurur. Aktarım kaydı uygulama imajına eklenmez ve Google çağrıları açılmaz. Kullanım geçmişi gerçekten yoksa `initialize-empty-ledger` yalnızca ilk kurulumda kullanılabilir. Mevcut guard veya kullanım kaydı varken yeniden başlatma olarak kullanılamaz. Guard ayrı dizinde tutulur; veritabanı kaybolur veya eski yedeğe dönerse Google çağrıları kapanır. Guard kaybolursa otomatik yeniden oluşturulmaz; eski kayıtlar ve Cloud Billing uzlaştırılır.

Anahtar yalnızca üç Google API'sine ve sunucunun çıkış IP'sine sınırlandırılır. Ana yerel uygulamadaki ücretli çağrılar kapalı kalır; tek onaylı yerel pilot yalnızca yukarıdaki ayrı, korumalı süreçte çalışabilir. Normal sağlık kontrolü Google'a istek göndermez. Genel günlük 33 deneme yanında Geocoding toplam 3, Nearby Search 3, Routes 27 sınırı backend'de de uygulanır. Başarısız ve yeniden denenen istekler de sayılır.

Google başlangıçta kapalıdır. Pilot için vergi ve kur dâhil ihtiyatlı birim TL fiyatları, kaynakları ve doğrulama zamanı girilir. Fiyat bilgisi eksik veya yedi günden eskiyse çağrılar durur. İlk pilot bütçesi en fazla 100 TL'dir; ileride ayrıca onaylanmış kullanım bile 1.200 TL güvenlik rezervini aşamaz. Ön ödeme, kullanım hedefi ve kesin tahsilat tavanı değildir. [Google fiyatları](https://developers.google.com/maps/billing-and-pricing/pricing)

## Başlatma ve kabul

```bash
python3 operations.py apply
docker compose exec ollama ollama list
sudo python3 operations.py warmup
docker compose exec api python scripts/evaluate_preferences.py --repeats 3 --output /backups/llama-acceptance.json
```

`warmup` yalnızca kurulu `llama3:8b` modelini belleğe yükler; eksik modeli otomatik indirmez. `OLLAMA_KEEP_ALIVE=-1` modelin bellekte kalmasını sağlar. Açılış için `ortak-model-warmup.service` kurulur; model sunucuda zaten kurulu değilse operatör kontrollü tek indirme ayrıca yapılır. İlk soğuk denemedeki 35/36 raporu silinmez. Kabul için yeni deneyde 36/36 kontrol, her istekte en fazla 120 saniye ve bellek taşması olmaması gerekir. Model mevcut diye anlamsal doğruluk kabul edilmez. Manuel kontroller model kesintisinde kullanılabilir.

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
sudo systemctl enable --now ortak-model-warmup.service ortak-health.timer ortak-backup.timer
```

Sağlık kontrolü beş dakikada bir HTTPS, SQLite, model listesi, disk ve konteyner durumunu okur; ücretli Google çağrısı veya model üretimi yapmaz. Ham tercih, konum, IP, model yanıtı ve sorgu parametreleri günlüğe yazılmaz. 24 saatlik gözlemde başarısız kontrol veya on dakikayı aşan boşluk gözlem süresini yeniden başlatır. API çökünce oturumluk konumlar kaybolur.

SQLite backup API'siyle günlük tutarlı yedek alınır; son yedi kopya özel tutulur. Sağlık kayıtları `deploy/private/` altındadır. Bunlar GitHub'a gönderilmez. Kullanıcının isteğiyle Codex yayın takip otomasyonu silindi. Sunucu timer'ları kurulursa bilgisayardan bağımsız çalışır; kurulduğu ayrıca doğrulanmalıdır.

## Geri dönüş ve kurtarma

Google çağrılarını kapattıktan sonra `python3 operations.py rollback` önceki imajlara döner; veri, guard, model ve sertifika dizinlerine dokunmaz. Eski SQLite dosyasını çalışan veritabanının üzerine yazmak yasaktır. Felaket kurtarmada API durdurulur, özel yedek ayrı konuma doğrulanır ve en güncel ledger ile birleştirilir. Kaybolmuş kullanımı doğrulamak mümkün değilse Google kapalı kalır. Guard'ı silmek veya sayacı düşürmek kurtarma yöntemi değildir.

## Tamamlanma ölçütü

GitHub deposu, ARM64 imajlar, sunucuda Llama kabulü, ayrıca onaylı Google pilotu, dış istemciden HTTPS ve öneri doğrulaması, yedekten kurtarma ve kesintisiz 24 saatlik sağlık gözlemi birlikte tamamlanmalıdır. Son teslimde sürüm etiketi, temizlenmiş sonuç özeti ve tamamlandı–eksik–engelli listesi verilir. Silinen Codex otomasyonu kendiliğinden yeniden kurulmaz. Ücretsiz kaynakların kesintisiz çalışması garanti değildir; yapay yük üreterek Oracle'ın boşta kalma kuralları aşılmaz.
