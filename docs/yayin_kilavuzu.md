# ORTAK Ücretsiz Yayın Kılavuzu

ORTAK, ücretsiz Oracle Ampere sunucusunda Caddy, FastAPI ve Ollama ile çalışan kontrollü bir betadır. Bu kılavuz hazırlık, kurulum, test, izleme ve kurtarma adımlarını kapsar. Kodun GitHub'a gönderilmesi tek başına sunucu kabulü değildir; aşağıdaki kayıtlar gerçek sunucu kanıtlarını ayrı gösterir.

## 13 Kasım 2026: Vercel Korundu, Ana Adres Birleştirildi

- Kullanıcının son tercihiyle Vercel'den Oracle'a arayüz taşıma işlemi iptal edildi. Arayüz Vercel'de; API, kalıcı kullanım kaydı ve Ollama Oracle'da kalır. Gateway istek bazlı HTTPS vekilidir; kişisel bilgisayarda açık tutulması gereken bir tünel yoktur.
- `ortak.web.tr` DNS kaydı çözülüyor. Vercel yönetim API'si alan adını doğrulanmış, DNS yapılandırmasını hatasız ve SSL sertifikasını verilmiş olarak gösterdi.
- `ortak-2209.vercel.app` ve `orak-2209.vercel.app` için ana adrese 308 yönlendirmeleri kaydedildi ve yönetim API'sinden tekrar okundu. `www.ortak.web.tr` yönlendirmesi korundu. Ana adres başka adrese yönlenmiyor; döngü yok. Bu ayarlar proje alan adı katmanındadır; yeni uygulama derlemesi gerektirmez. Eski adreste açık kalmış oturumlar ana adreste yeniden oluşturulur.
- Mevcut üretim dağıtımı değiştirilmedi. Yeni iki motorlu web/mobil kaynakları ayrı yayın hazırlığıdır. Oracle yönetimi yeniden giriş istediğinden yeni API imajı henüz sunucuya uygulanmadı. Yeni motorların üretim kabulü tamamlandı denemez.
- Yerelde 319 backend, 42 masaüstü/mobil web ve 9 gateway/aktarım testi geçti. Mobilde 25 test, TypeScript ve üç platform export başarılıdır. Gerçek yerel `llama3:8b` plan yorumlama seti 5/5 geçti; Google çağrısı yapılmadı. Bu, Oracle model kabulü veya mağaza yayını değildir.
- Canlı sitenin görsel testi kayıtlı tarayıcı erişim iznine takıldı; alternatif tarayıcı veya HTTP istemcisiyle bu engel aşılmadı. DNS/sertifika/yönlendirme yönetim kayıtları, uçtan uca tarayıcı kabulünden ayrı tutulur. Yeni ödeme, kaynak veya otomasyon oluşturulmadı.

## 12 Kasım 2026: Özel Alan Adı

- `ortak.web.tr` beş yıllığına tescil edildi; otomatik yenileme kapatıldı. Ek hosting, e-posta veya SSL paketi alınmadı. Ödeme belgeleri özel mali arşivde tutulur.
- Alastyr ParkDNS üzerinde `@` ve `www` A kayıtları `76.76.21.21` adresine yönlendirildi. İki adres mevcut `ortak-2209` Vercel projesine eklendi; `www` için ana adrese 308 yönlendirmesi tanımlandı. Oracle API ve Llama taşınmadı.
- Canlı Vercel sürümünün kaynakları alınarak yalnızca gateway'in tam alan adı izinlerine `https://ortak.web.tr` ve `https://www.ortak.web.tr` eklendi. İlgisiz yerel mobil/tema değişiklikleri yayımlanmadı. Alt alan adı taklitleri ve HTTP reddedilir; oturum ve CSRF kontrolleri korunur.
- Altı gateway testi ve üretim derlemesi başarılıdır. `dpl_HtcXQUYETCihBbNduEiVVjACATr1` üretime alındı; önceki sürüm `dpl_75y2ZRNUyfh3catooa8zdg6TomUa` geri dönüş için korunur. Yayın öncesi geçici test erişimi kaldırıldı.
- Mevcut Vercel adresinde sağlık yanıtı başarılı, gerçek `llama3:8b` hazır ve yeni Google arama kapasitesi açık görüldü. Bu alan adı değişikliği için ücretli Google çağrısı veya yeni Llama üretimi yapılmadı.
- Son kontrolde TRABİS yetkili DNS sunucusu henüz alan adını yayımlamıyordu. Yeni adreste dış HTTPS ve tarayıcı kabulü bu nedenle tamamlanmış sayılmaz. Ayrıca mevcut Vercel adresinin görsel testi, Codex'in kayıtlı tarayıcı erişim iznine takıldı. DNS yayılımından ve erişim izninden sonra ana adres/`www`, HTTPS, oturum ve öneri akışı doğrulanmalıdır. Özel takip kaydı: `output/deployment/domain-20261112/`.
- Aynı gün Alastyr canlı desteği, nameserver değişikliğinin yeni olduğunu ve çözümlenmenin birkaç saat sürebileceğini bildirdi. Bu yanıt DNS/HTTPS kabulü yerine geçmez; DNS kayıtlarını yeniden oluşturmak veya yeni ücretli hosting almak gerekmez.
- Son yerel teknik kontrolde 286 backend testi, 6 gateway testi ve 23 mobil test geçti; web derlemesi, mobil TypeScript/native yapılandırma ve üç platform export başarılıdır. Gateway testleri CI yapılandırmasına eklendi. Bu hazırlık değişiklikleri henüz GitHub'a gönderilmedi ve yeni bir canlı sürüm yayımlanmadı.

## 7 Kasım 2026: Günlük Pilot Sınırının Kaldırılması

- [ORTAK](https://ortak-2209.vercel.app/) arayüzü Vercel'de, API ve gerçek `llama3:8b` mevcut Oracle sunucusunda çalışır. Bu bölüm güncel durumu gösterir; aşağıdaki tarihli bölümlerin sınır ve kapasite değerleri geçmiş kayıtlarıdır.
- Kullanıcının açık isteğiyle `GOOGLE_DAILY_QUOTA_ENABLED=false` canlıya uygulandı. Uygulamadaki günlük 33 ve servis bazlı 3/3/27 durdurma koşulları artık uygulanmaz. Önceden kaldırılan toplam 100 TL sınırı da kapalıdır. Kalıcı kullanım kaydı, guard, fiyat doğrulaması ve kısa süreli oturum/IP hız sınırları korunur; sayaç sıfırlanmadı.
- Google projesinde Nearby Search günlük sınırı pilot değerinden 75.000 varsayılanına, Geocoding ve Compute Routes günlük sınırları sınırsız değerine getirildi. Google'ın dakika başına kotaları ve hizmet koşulları devam eder. Bu değişiklik ücretsiz veya kesintisiz kullanım garantisi değildir; yeni kullanım hesaba ücret yansıtabilir.
- `404dd5f` sürümünün 247 backend testi ve [CI/ARM64 işleri](https://github.com/tunayalc/ortak/actions/runs/42350992112) başarılıdır. Sabitlenmiş API imajı mevcut sunucuya kuruldu. Doğrulama, dağıtım, Google etkinleştirme, model hazırlığı, sağlık ve yedekleme görevleri başarılı tamamlandı.
- Gerçek üretim tarayıcısı kabulü 25/25 geçti. Llama yanıtı 62,931 saniyede alındı; kullanıcı onayı öncesi değerlerin korunması ve onay sonrası 2/1/1 kişi ağırlıkları doğrulandı. Üç gerçek Google mekânı ve dokuz geçerli rota için 1 Places + 9 Routes çağrısı yapıldı; yeniden deneme olmadı. Profil, kişi ağırlığı ve filtre değişiklikleri ek Google çağrısı üretmedi.
- 390/1440 piksel, açık/koyu tema, klavye kullanımı ve yalnızca hedefi içeren yol tarifi bağlantıları başarılıdır. Test senaryosu silindi. Testten sonra Google araması hâlâ kullanılabilir, Llama hazır ve HTTPS sağlık yanıtı başarılıdır. Özel kabul kaydı `output/deployment/daily-quota-live-20261107/run.json` altında tutulur; ham konum, tercih veya Google içeriği içermez ve GitHub'a gönderilmez.
- Geçici seri konsolun `DELETED` durumu doğrulandı; bu bakıma ait Cloud Shell anahtarları ve terminal oturumu kaldırıldı. Kalıcı yetki genişletilmedi. Mevcut diskler, model ve kullanım geçmişi korundu; yeni sunucu, ödeme veya bakiye yükleme yapılmadı. Silinen Codex otomasyonu yeniden kurulmadı.

## 6 Kasım 2026: Vercel ve Toplam Bütçe Sınırı

- Güncel arayüz adresi [ORTAK](https://ortak-2209.vercel.app/); FastAPI ve `llama3:8b` mevcut Oracle sunucusunda çalışır. Aşağıdaki tarihli kabul kayıtları geçmiş sürümlerin kanıtlarıdır.
- Kullanıcının açık isteğiyle toplam 100 TL durdurma koşulu kaldırıldı: `GOOGLE_LIFETIME_BUDGET_ENABLED=false`. Bu ayar günlük Google kotalarını, hız sınırlarını, fiyat doğrulamasını veya kalıcı kullanım kaydını kapatmaz. `GOOGLE_BUDGET_ENFORCEMENT_ENABLED=true` korunur; API `budget_enforced=false`, `budget_limit_tl=null`, `usage_accounting_enforced=true` döndürür.
- İstek başına deneme sayısı `1` oldu. Günlük 33 ve Geocoding/Places/Routes için 3/3/27 sınırları korunur. Bu yüzden toplam TL tavanı olmaması, sınırsız günlük arama veya ücretsiz Google kullanımı anlamına gelmez.
- `394ada4` sürümü için 238 backend testi, gateway testleri, üretim derlemesi ve [CI/ARM64 işleri](https://github.com/tunayalc/ortak/actions/runs/42257794890) başarılıdır. Doğrulanmış API imajı sunucuya uygulandı; sayaç ve guard yeniden oluşturulmadı. Sunucu model hazırlığı ve sağlık işlemleri başarılıdır.
- Geçici seri konsol ve yalnızca bu bakım için oluşturulan Cloud Shell anahtarı kaldırıldı. Yeni sunucu, ödeme veya bakiye yükleme yapılmadı; ücret doğurabilecek Google kullanımı mevcut hesaptan devam eder.
- `frontend/tests/live_acceptance.mjs` toplam tavanın kapalı olduğu kabul için ayrıca `ORTAK_LIVE_UNCAPPED_APPROVED=1` ister. Test başına 100 TL onay bayrağı, uygulamanın genel bütçesi değildir; tek denemeyle planlanan 10 Google isteğini sınamak içindir. Canlı rapor özel `output/deployment/uncapped-live-20261106/` dizinindedir ve GitHub'a gönderilmez.
- Yeni yapılandırmayla gerçek üretim tarayıcısı kabulü 24/24 geçti. Llama yanıtı 62,42 saniyede geldi; kullanıcı onayı, 2/1/1 kişi ağırlıkları, üç Google adayı ve dokuz geçerli rota doğrulandı. 1 Places + 9 Routes isteği yapıldı; yeniden deneme olmadı. Profil, delta ve filtre değişiklikleri ek Google çağrısı üretmedi. 390/1440 piksel, açık/koyu tema ve klavye kontrolleri başarılıdır. Test oturumu silindi. Son kontrolde 13 günlük istek ve üç kişilik yeni arama kapasitesi vardı; bu sayı yeni kullanımla değişir. Gerçek fatura tutarı bu test raporundan çıkarılamaz.

## 27 Ekim 2026: Güncel Kurulum

- Güncel adres [ORTAK](https://158.180.36.171.nip.io/). Aşağıdaki 14 ve 17 Ekim kayıtları eski sunucuya aittir; eski adres ve 24 saatlik kabul yeni sunucuya taşınmış sayılmaz.
- `46faebb` düzeltmesinin [CI çalışması](https://github.com/tunayalc/ortak/actions/runs/40321756634) başarılıdır: 232 backend testi, 34 arayüz testi ve iki ARM64 imajı geçti. Yeni API imajı mevcut sunucuya uygulandı; kurulu model ve kullanım kayıtları yeniden oluşturulmadı.
- Fiyat yenilemenin Google çağrılarının açık olmasına bağlı kalması giderildi. Ücretli Google çağrıları kapalıyken resmî, herkese açık kaynaklardan fiyat yenileme ve servis kota bilgisinin okunması canlı sunucuda doğrulandı. Bu işlem ücretli Maps isteği değildir.
- Son dış kontrolde HTTPS, `/api/readyz` ve `/api/health` başarılı, `llama3:8b` hazırdır. Google çağrıları henüz kapalıdır; arayüz bunu gösterir ve öneri üretimini engeller. Bütçe ve mevcut guard doğrulanarak etkinleştirme tamamlanmadan ücretli öneri akışı kullanılabilir sayılmaz.
- Mevcut 100 TL toplam koruma, günlük sınırlar ve kullanım geçmişi korunur. Silinen Codex otomasyonu yeniden kurulmaz. Bu güncellemede yeni ücretli Google testi veya ödeme yapılmadı.

## 17 Ekim 2026: Canlı Yayın Kabulü

- Canlı adres: [ORTAK](https://92.5.80.85.nip.io/). Ön yüz, API ve gerçek `llama3:8b` Oracle'da çalışır; kişisel bilgisayarın açık kalması gerekmez.
- 24 saatlik gözlem koşulu tamamlandı. Sunucu kaydı yaklaşık 78,45 saat kesintisiz sağlık gösterdi; son 24 saatte 282 kontrol başarılı, en büyük kontrol aralığı 311,053 saniye.
- Üç konteyner çalışıyor; bellek taşması ve konteyner yeniden başlatması görülmedi. Docker ve model açılış birimi etkin; sağlık ve günlük yedek zamanlayıcıları etkin ve çalışır durumda. Güncel yedeğin SQLite bütünlüğü ve 43 kullanım kaydı doğrulandı.
- Google kullanımı açık; günlük kota yenilenmiş ve varsayılan üç kişilik yeni arama kapasitesi kullanılabilir. Mevcut toplam 100 TL ihtiyatlı maliyet koruması ve günlük 33 deneme sınırı değişmedi. Bu kontrolde yeni Google çağrısı veya ödeme yapılmadı.
- Modelin açılışta yüklenmesini Google çağrıları açıkken engelleyen yönetim betiği düzeltildi. Sadece kurulum/geri dönüş işlemleri çağrıların kapalı olmasını zorunlu tutar; yalnızca kurulu yerel modeli yükleyen açılış işlemi bu ayarı değiştirmez, model indirmez ve Google çağrısı yapmaz. Düzeltme sunucudaki gerçek systemd birimiyle doğrulandı.
- Son [CI çalışması](https://github.com/tunayalc/ortak/actions/runs/39008985607): 171 backend ve 34 arayüz testi, API/web ARM64 imajları başarılı. Yönetim betiği `6c978ac` sürümüne alındı. Uygulama kodu değişmediği için kabulü geçmiş `8f8f34f` imajları korunarak servis kesintisi ve oturum kaybı önlendi.
- Son ücretsiz üretim tarayıcısı kontrolü sağlık, Llama hazırlığı, gerçek kota ile düğme uyumu ve 390/1440 pikselde klavye kullanımını doğruladı. Gerçek ücretli öneri kanıtı 14 Ekim'deki Llama–Google–dokuz rota–kart akışıdır; bu tur o ücretli test tekrarlanmadı.

Özel kanıtlar `output/deployment/persistent-release-20261017.json` ve `output/deployment/browser-live-20261017-readiness/` altında tutulur; ham konum, tercih, Google içeriği veya anahtar içermez ve GitHub'a gönderilmez. Silinen Codex otomasyonu yeniden kurulmadı; mevcut sunucu zamanlayıcıları kişisel bilgisayardan bağımsızdır.

**Süreklilik sınırı:** Site ve yerel model sunucuda açık kalır; Google araması kota, mevcut toplam bütçe ve yedi günlük doğrulanmış fiyat kaydıyla sınırlıdır. Bu korumalar kendiliğinden kaldırılmaz. Bütçe dolarsa, günlük kapasite yetmezse veya fiyat bilgisi eskirse yeni ücretli arama durur; site ve manuel tercihler erişilebilir kalır. Fiyat yenilemesi resmî kaynaklarla doğrulanmalı; bütçe artışı ayrı kullanıcı onayı gerektirir. Oracle Always Free kaynakları için kesintisiz veya süresiz hizmet garantisi verilmez.

## 14 Ekim 2026 Durumu

| Kontrol | Durum |
| --- | --- |
| Backend testleri | 167/167 başarılı; servis fiyatlarıyla ön hesap, çözümlenmiş konumun yeniden ücretlendirilmemesi, eksik rota tamamlaması ve tam matris zorunluluğu test edildi |
| Mobil ve masaüstü arayüz testleri | 34/34 başarılı; 390 ve 1440 piksel, açık/koyu tema, klavye odağı, kota yenileme, koordinat aktarımı ve kesilen rota akışı sınandı |
| Gerçek yerel Llama 3 8B | 36/36 başarılı; ortalama 2,10 sn, azami 6,87 sn; Oracle performansı değildir |
| GitHub Actions ve ARM64 imajları | Canlı kabulün çalıştığı `2ed0711` için [iş akışı 38484704103](https://github.com/tunayalc/ortak/actions/runs/38484704103) başarılı. Klavye testini düzelten `8f8f34f` için de [iş akışı 38485538601](https://github.com/tunayalc/ortak/actions/runs/38485538601) başarılı: 167 backend, 34 arayüz testi ve iki ARM64 imajı geçti |
| Tutarlı SQLite yedeği | Birim testlerinde ve ARM64 konteynerinde doğrulandı |
| GitHub deposu | [tunayalc/ortak](https://github.com/tunayalc/ortak) açık; `2ed0711` uygulama sürümü gerçek üretim tarayıcısında sınandı. Sunucuda son `8f8f34f` CI imajları çalışıyor; bu sürüm yalnızca test araçlarını değiştiriyor, uygulama kodu aynı |
| Oracle hesabı ve ücretsiz kapasite | Frankfurt AD-1'deki eski `ortak-beta` ve 50 GB boot diski sonlandırıldı. Yalnızca `ortak-beta-yeni` 2 OCPU/12 GB ve yaklaşık 47 GB boot diskiyle çalışıyor. Kısa süreli sunucu örtüşmesinin deneme kredisi kullanımına etkisi fatura ekranından ayrıca kontrol edilmeli |
| Dış HTTPS | [Yeni sunucu](https://92.5.80.85.nip.io/) ve `/api/health` dışarıdan HTTPS 200 döndü; sertifika doğrulaması başarılı. On eşzamanlı `/api/readyz` isteği 200 döndü; API ve Ollama portları dışarıdan erişilemedi |
| Sunucuda Llama 3 8B | İlk soğuk deney 35/36 idi: ilk istek 120,136 saniye. Başarısız rapor ayrı saklandı. Açılış yüklemesinden sonraki gerçek deney 36/36 geçti; en yavaş yanıt 51,756 saniye ve üç konteynerde OOM yok |
| Canlı tarayıcıda Llama ve Google | Gerçek HTTPS uygulamasında Llama 20,972 saniyede fiyat önceliği ve 2/1/1 kişi ağırlığı önerdi. Önizleme onayından sonra üç Google mekânı ve dokuz Google rotasıyla kartlar oluştu. Profil, kişi ağırlığı ve filtre değişiklikleri ek Google çağrısı üretmedi |
| Sağlık ve yedek | Model açılış servisi ile sağlık/yedek zamanlayıcıları etkin. Canlı tarayıcı kabulü sonrası ayrı SQLite yedeğinden 43 kullanım kaydı geri okunarak bütünlük ve guard eşleşmesi doğrulandı; üretim sayacı değişmedi |
| Google ve 24 saat gözlem | Yerel ve Oracle pilotları ayrı ayrı 13/13 geçti. Son üretim tarayıcısı akışı 10 gerçek Google isteğiyle tamamlandı. Toplam kayıt 43, ihtiyatlı rezerv 69,30 TL; 100 TL koruma içindeki kalan rezerv 30,70 TL. Günlük Places/Routes hakları dolduğu için yeni arama kapalıdır; mevcut sonuç güncellemeleri ücretsizdir. Nihai 24 saatlik gözlem henüz tamamlanmadı |

14 Ekim'de kullanıcı, önceki 10.00 bekleme koşulunu açıkça değiştirerek yerel pilotun hemen başlatılmasını istedi. Onaylı 100 TL sınırıyla 11 gerçek Google isteği yapıldı; yeniden deneme olmadı. Bu, genel doğruluk veya Google faturası hakkında kesin bir iddia değildir. Bu yerel çalışma sırasında ücretli sunucu, ödeme işlemi veya ikinci Google pilotu başlatılmadı; daha sonraki ayrı Oracle pilotu aşağıda açıklanır.

## Üretim Tarayıcısı Kabulü

`2ed0711` sürümü başarılı CI ve ARM64 imajlarından HTTPS üretim sunucusuna taşındı. Üç kurgusal katılımcının koordinatlarıyla gerçek Llama önizlemesi, kullanıcı onayı, Places araması, tam rota matrisi ve kriter bazlı öneri kartları aynı tarayıcı oturumunda çalıştırıldı. Konumlar modele gönderilmedi; onay öncesinde mevcut tercihler değişmedi. Llama fiyat ağırlığını 70, diğer iki kriteri 34/33 ve kişi ağırlıklarını 2/1/1 önerdi. Önerilerde kişi katkıları 0,50/0,25/0,25 olarak doğrulandı.

Sonrasında `8f8f34f` test aracı sürümünün başarılı CI imajları da sunucuya alındı. `backend/app` ve `frontend/src` kodları ücretli kabulün geçtiği sürümle aynıdır; ikinci ücretli arama yapılmadı. Son imajlarda sağlık, koruma, kota görünümü ve klavye davranışı ücretsiz canlı kontrolle yeniden doğrulandı.

Test boyunca istek başına tek deneme kullanıldı: 0 Geocoding, 1 Places ve 9 Routes, toplam 10 başarılı Google isteği; yeniden deneme yok. İhtiyatlı rezerv artışı 11,25 TL'dir, fatura tutarı değildir. Başlangıçtaki 33 kayıt ve 58,05 TL rezerv korundu; sonuçta 43 kayıt ve 69,30 TL oldu. Normal iki denemelik ayar geri yüklendi. Aynı sonuçlarda dört kriter profili, dengeli kişiler, kişi ağırlığı ve filtre değişiklikleri ücretli çağrı üretmedi. Yol tarifi bağlantıları yalnızca hedef mekânı içerdi. Sonuç kartları 390/1440 pikselde, açık/koyu temada yatay taşma üretmedi. Test senaryosu sonunda silindi; kalıcı konum, aday, rota ve Google cache tabloları boş.

İlk koşunun bütün ücretli akış ve yerleşim kontrolleri geçti; son klavye kontrolü, seçenek metinlerini de içeren etiket için yanlış `exact` seçicisi nedeniyle başarısız kaydedildi. Bu rapor değiştirilmedi. Seçici düzeltildi; üretim sayfasında ayrı, sıfır Google ve sıfır model üretimi yapan kontrolle mobil/masaüstü klavye odağı ve kota uyarısı doğrulandı. Bu ek kontrol, ikinci bir ücretli arama değildir. Başarı özeti iki kanıtı birlikte değerlendirir; hata geçmişi korunur.

Özel raporlar `output/deployment/browser-live-20261014-production/` ve `output/deployment/browser-live-20261014-keyboard-corrected/` altında tutulur. Yalnızca sürüm, süre, HTTP durumu, çağrı sayıları ve kontrol sonuçları kaydedilir; anahtar, oturum çerezi, ham tercih, koordinat ve Google yanıt içeriği yazılmaz. Otomatik CI testleri canlı ücretli testi kendiliğinden başlatmaz.

`/locations/parse` sonucundaki koordinatlar senaryo isteğinin `value` alanına aktarılır; formdaki özgün link korunur. Kriter veya kişi ağırlığı değişikliği parse işlemini tekrarlamaz. Ön hesap her servisin doğrulanmış fiyatını ve yapılandırılmış deneme sınırını kullanır. `/runtime-config` içindeki `google_search_capacity`, sentetik/çözümlenmiş koordinat modları ve kişi sayısı için Türkçe kapasite durumunu sunar; arama öncesi ve sonrası yenilenir. Kesilen matris aynı senaryoda yalnızca eksik kişi–mekân çiftlerini tamamlar; tam Google matrisi olmadan öneri sunulmaz.

Yeniden ücretli test ancak mevcut kayıt ve kotalar uzlaştırıldıktan, ilgili onay doğrulandıktan sonra yapılır. Sadece sağlık, kota görünümü ve klavye kontrolü için ücretli akışa gerek yoktur:

```bash
cd frontend
npm run test:live:read-only
```

Bu komut yalnızca HTTPS sayfasını ve sağlık/yapılandırma uçlarını okur. `npm run test:live` ise açık onay bayrakları, tek deneme, mevcut 100 TL koruması ve yeterli servis kotası ister; kendiliğinden tekrar çalıştırılmamalıdır. Nihai yayın kabulü, mevcut sunucu sağlık zamanlayıcısında 24 saatlik gözlem tamamlanınca verilir. Silinen Codex otomasyonu yeniden kurulmadı.

Son sürümün sağlık ve ücretsiz tarayıcı kontrollerinden sonra gözlem başlangıcı 14 Ekim 2026 02.45 Türkiye saati olarak kaydedildi. Hata veya uzun kontrol boşluğu yaşanmazsa en erken 15 Ekim 2026 02.45'te 24 saat koşulu sağlanabilir; bu saatin gelmesi tek başına kabul değildir, sunucu gözlem kaydı ayrıca okunmalıdır. Beş dakikalık sağlık ve günlük yedek zamanlayıcıları etkin; Google çağrısı veya Llama üretimi yapmazlar.

## Ayrı Yerel Google Pilotu

14 Ekim'de kullanıcı, genel öneri kullanımını sunucudaki mevcut toplam 100 TL tahmini maliyet korumasıyla açmayı ayrıca onayladı. Üretim backend'inde `GOOGLE_MAPS_CALLS_ENABLED=true` etkinleştirildi; günlük 33 ve 3/3/27 servis sınırları, iki denemelik istek sınırı ve mevcut ledger/guard korundu. HTTPS sağlık kontrolü ve tarayıcıdaki etkin öneri formu doğrulandı. Açılış kontrolünde yeni Google isteği yapılmadı. O anda günlük 11 istek ve 1/1/9 servis hakkı, yani üç kişi ve üç aday için bir normal tam arama kaldı. Toplam ihtiyatlı rezerv 58,05 TL, kalan rezerv 41,95 TL idi; yeni kullanımla değişir ve Google faturası değildir. Ücretli kullanım fiyat bilgisi eskidiğinde, bütçe veya kota dolduğunda kapanır. Nihai üretim tarayıcısı öneri akışı ve 24 saat kabulü ayrı takip edilir.

Oracle pilotunu mevcut kotayla çalıştırmak için `GOOGLE_MAPS_MAX_ATTEMPTS=2` kullanılabilir. Bu ayar her Google isteğini en fazla iki denemeyle sınırlar; pilotun en kötü durumda 22 deneme ve 2 Geocoding / 2 Places / 18 Routes hakkı gerekir. İhtiyatlı azami rezerv 23,40 TL'dir. Varsayılan üç denemede 33 ve 3/3/27 gereksinimi korunur. Günlük kota, bütçe ve kullanım kaydı değişmez; test ön kontrolü gerçek backend tekrar sınırını kullanır.

Kullanıcı, mevcut Ollama `llama3:8b` modeliyle yalnızca Google Maps için en fazla 100 TL kapsamını seçti ve aşağıdaki maliyet tahminiyle tek yerel pilotu onayladı; ücretli model barındırma seçilmedi. Yerel pilot 14 Ekim'de tamamlandı. Kullanıcı, bunun ardından Oracle'da ayrı ve yine en fazla 100 TL'lik ikinci bir pilotu da onayladı; bu pilot da gerçek sunucu modeli ve Google servisleriyle tamamlandı. Yerel sonuç Oracle sunucu kabulü yerine kullanılmadı.

Oracle pilotunda yeniden deneme sınırı ikiye düşürüldü; mevcut 22 deneme ve 2/2/18 servis hakkı yeterliydi. Gerçekte yalnızca 11 Google isteği gönderildi, yeniden deneme olmadı ve 13/13 kontrol geçti. Oracle Llama yanıtı 23,547 saniyede beklenen kriter ve kişi ağırlıklarını verdi. Pilotun ihtiyatlı rezervi 11,70 TL; bu değer Google faturası değildir. Kriter/kişi değişiklikleri yeni rota çağrısı üretmedi. Özel rapor `output/google_maps/oracle-approved-20261014/` dizininde tutulur. Geçici sunucu süreci ve SSH tüneli kapatıldı. Yerel ve sunucu kullanım kayıtları 33 satırla uzlaştırıldı; iki guard doğrulandı. Gerçek konum/Google içerik tablolarında kalıcı kayıt yok. Genel ücretli kullanımı açmak, önceki pilot onayının dışındaki ayrı kapsamdır.

14 Ekim çalışması öncesinde yeniden doğrulanan [Google fiyatları](https://developers.google.com/maps/billing-and-pricing/pricing): Geocoding 0,005 USD, Nearby Search Enterprise 0,035 USD, trafik verili Compute Routes Pro 0,010 USD/istek. Üç kurgusal kişi ve üç aday için 11 normal çağrı 0,13 USD, tüm istekler iki kez yeniden denenirse 33 deneme 0,39 USD eder. [Google Türkiye KDV oranı %20'dir](https://docs.cloud.google.com/billing/docs/resources/vat-overview). [TCMB'nin 13 Ekim bülteni](https://www.tcmb.gov.tr/kurlar/today.xml) USD döviz satışını 49,3681 TL gösterdi. Bu TCMB değeri Google'ın fatura kuru değildir.

İhtiyatlı rezervasyonda 60 TL/USD ve ayrıca %25 güvenlik payı kullanıldı: normal 11,70 TL, azami 35,10 TL. Ücretsiz kullanım düşülmedi; gerçek fatura daha düşük veya sıfır olabilir. Rezervasyon banka tahsilatı için kesin tavan değildir. Kaynaklı özel fiyat kaydı ve ön kontrol sonucu GitHub dışında tutulur; çalıştırmadan önce fiyat, kur, vergi ve servis kotaları yeniden doğrulanır.

Yerel pilot öncesi backend'de 33 deneme, Google konsolunda Geocoding 3, Places 3, Routes 27 günlük hak vardı. Pilot sonrası mevcut gün için yerel kalan haklar 22 ve servis bazında 2/2/18 oldu. [Google günlük kotası Pasifik gece yarısında yenilenir](https://developers.google.com/maps/documentation/geocoding/usage-and-billing); ikinci pilot için Google kotaları ile taşınmış backend sayacı birlikte yeniden doğrulanır. Sayaçlar sıfırlanmaz ve kota artırılmaz.

Onaylanan yerel pilot ayrı ve yalnızca `127.0.0.1` üzerinde erişilen geçici backend'de çalıştırılır. Ana uygulamadaki ücretli çağrılar kapalı kalır. Mevcut veritabanı ve guard dosyasının mutlak yolları doğrulanıp aynı kullanım kaydı kullanılır; yeni bir boş veritabanıyla kotayı yeniden başlatmak yasaktır. Geçici backend için `GOOGLE_BUDGET_ENFORCEMENT_ENABLED=true`, `GOOGLE_BUDGET_LIMIT_TL=100`, doğrulanmış birim TL rezervleri ve fiyat kaynakları zorunludur. Bu ayarlar örnek dosyada bulunur; gerçek anahtar paylaşılmaz. Bütçe koruması, fiyat veya guard eksikse test Google'a istek göndermez.

```bash
cd backend
.venv-release/bin/python scripts/evaluate_google_maps.py --api-base http://127.0.0.1:8012 --live --with-llama --max-spend-tl 100
```

Bu komut yalnızca son onay, yeterli kota ve korumalı geçici backend hazırken çalıştırılır. 14 Ekim yerel pilotunda gerçek Llama'nın `2x/1x/1x` kişi ve puan/fiyat/yakınlık tercihi Google aramasından önce doğrulandı. Üç kişi x üç aday için tam dokuz Google rotası alındı. Profil ve kişi tercihi değişiklikleri ek çağrı üretmedi; 13/13 kontrol geçti. Test raporu GitHub dışındaki `output/google_maps/local-approved-20261014-early/` dizinindedir. Ham tercih, koordinat ve Google içerikleri kaydedilmez. Yerel pilot sonrası toplam kullanım kaydı 22 satır ve rezerv 46,35 TL idi; ayrı Oracle pilotu sonrası toplam 33 satır ve 58,05 TL oldu. Bunlar ihtiyatlı rezervlerdir; fatura tutarı değildir. Başka bir pilot mevcut kayıt uzlaştırılmadan ve ayrı kapsam belirlenmeden tekrarlanmaz.

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

### IP'den bağımsız kalıcı yönetim

Oracle Linux 9 sunucusu, Oracle'ın Run Command kanalıyla yönetilebilir. Bu kanal için bilgisayarın değişen IP adresini SSH listesine eklemek veya özel SSH anahtarını Cloud Shell'e yüklemek gerekmez. Kalıcı IAM izni ve sunucudaki sınırlı sudo izni ayrı güvenlik değişiklikleridir; ikisi de yalnızca kullanıcı açıkça onayladıktan sonra etkinleştirilir. Bu bölüm kurulum yöntemidir, mevcut sunucuda etkinleştirildiği iddiası değildir. [Oracle Run Command belgeleri](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm).

Dinamik grubun üyelik kuralı yalnızca tek ORTAK makinesinin `instance.id` değerini içermelidir. Gruba, `instance-agent-command-execution-family` için yalnızca kendi görevlerini alma ve sonuçlandırma izni verilir; `request.instance.id=target.instance.id` koşulu korunur. Başka makinelere, Object Storage'a veya genel kaynak yönetimine erişim verilmez. Komut gönderen yönetici mevcut Oracle kimlik doğrulamasını kullanır. [Resmî IAM örneği](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/instances.htm).

Sunucu tarafında `deploy/install_command_admin.sh --confirmed-permanent-instance-access`, kullanıcı onayının ardından root olarak çalıştırılır. Betik, root'a ait sınırlı bir başlatıcı kurar. `ocarun` hesabı yalnızca `/usr/local/sbin/ortak-admin` komutunu sudo ile çalıştırabilir; Docker grubuna eklenmez ve genel `NOPASSWD: ALL` yetkisi almaz. Mevcut beklenmeyen sudo erişimi varsa kurulum durur. Sudoers sözdizimi gerçek `visudo` ile doğrulanır.

İzin verilen işlemler `status`, `provision`, `verify`, `apply`, `rollback`, `warmup`, `health` ve `backup` ile sınırlıdır. `provision`, yalnızca ilk kurulumda yönetici tarafından yerleştirilen, root'a ait sabit `/usr/local/libexec/ortak-provision.py` dosyasını ek argümansız çalıştırır; kullanıcıdan betik veya dosya yolu almaz. Bu dosya yoksa ya da güvenli değilse işlem durur. Ek argüman, genel komut çalıştırma, bütçe değiştirme veya boş kullanım sayacı oluşturma seçeneği yoktur. Programlar ve özel yapılandırma root'a ait olmalı; sembolik bağlantılar ve başka kullanıcıların yazabildiği dosyalar reddedilir. Python yalıtılmış modda ve temiz ortam değişkenleriyle çalışır. İşlem kilidi çakışan yönetim görevlerini engeller. Alt süreç çıktıları Oracle komut yanıtına aktarılmaz; yalnızca kısa başarı/hata bilgisi döner.

```bash
sudo -n /usr/local/sbin/ortak-admin status
sudo -n /usr/local/sbin/ortak-admin health
```

`status` yanıtı yönetim kanalını ve Docker hizmetini doğrular; uygulamanın canlı kabulü değildir. `health` ve dış HTTPS kontrolü ayrıca geçmelidir. `apply` ve `rollback`, mevcut Google-kapalı kurulum kuralını korur. İmaj digest değerleri yönetici tarafından doğrulanmış üretim yapılandırmasından gelir; bu kanal her GitHub gönderimini otomatik yayımlamaz. `warmup` yalnızca kurulu Llama modelini yükler. Google bütçesi, günlük kota ve kullanım kaydı bu yetkiyle artırılamaz veya sıfırlanamaz. Sunucudaki mevcut yeniden başlatma, sağlık ve yedekleme hizmetleri ayrıca kurulur ve gerçek çalışma sonuçlarıyla doğrulanır.

Kalıcı yönetim kanalı SSH'yi internete açmaz; FastAPI ve Ollama portları da özel kalır. Oracle hesabının yetkisiz ele geçirilmesi yine risktir; hesap doğrulaması ve tek makineyle sınırlı IAM kuralı korunmalıdır. İlk kurulumda yönetim erişimi yoksa bu başlatıcı, aynı makinenin onaylı açılış yapılandırmasıyla kurulur; yeni ücretli kaynak açılmaz ve mevcut kullanım kaydı korunur.

Temiz kurulumda tercih edilen platform Oracle Linux 9 ARM64'tür. `deploy/bootstrap.sh`, önce platformu kontrol eder; Oracle Linux 9 ve mevcut Ubuntu 24.04 yolu dışında paket kurmaz. `bash deploy/bootstrap.sh --check-platform ol 9.7` komutu hiçbir sistem değişikliği yapmadan platform seçimini doğrular.

Oracle Linux yolunda Docker'ın imzalı EL9 paket deposu kullanılır; imza anahtarının parmak izi doğrulanmadan paketler kurulmaz. Docker'ın SELinux desteği etkinleştirilir ve API veri/guard/yedek bağlamaları özel `:Z` etiketiyle açılır. SELinux kapatılmaz. Ubuntu kurulumu korunur. Oracle Linux paket uyumluluğu, gerçek yeni ARM64 makinede `docker info`, `docker compose version` ve uygulama sağlık kontrolleriyle ayrıca doğrulanır; platform birim testi gerçek makine kurulumunun yerine geçmez. [Docker paketleri](https://docs.docker.com/engine/install/centos/), [Oracle'ın Docker deposu kullanan kurulum örneği](https://docs.oracle.com/en/solutions/oci-free-wordpress-docker/install-and-configure1.html).

Kurulum betiği SSH veya güvenlik duvarı kurallarını değiştirmez, Docker grubuna kullanıcı eklemez ve Run Command için sudo yetkisi vermez. Yönetim erişimleri yalnızca açıkça onaylanan kaynaklar için ayrıca kurulur ve uygulamadan önce sınanır. Mevcut sunucunun değiştirilmesi veya test senaryolarının silinmesi Google hesabının geçmiş harcamasını sıfırlamaz; mevcut kullanım kaydı uzlaştırılmadan ücretli Google çağrıları açılmaz.

Testleri geçen commit `/opt/ortak` içine alınır. Docker ve Compose resmî Docker kaynağından kurulur. `deploy/.env.example` üretim için örnektir; gerçek `.env` özel kalır ve `0600` izinle tutulur. Alan adı sunucu IP'sinin `nip.io` karşılığıdır. API ve web imajları başarılı GitHub Actions işinin ARM64 digest değerleriyle sabitlenir. İmajların sunucudan erişilebilirliği doğrulanır; paket görünürlüğü doğrulanmadan dağıtım hazır sayılmaz.

```bash
cd /opt/ortak/deploy
sudo install -d -m 700 -o 10001 -g 10001 data guard backups
install -d -m 700 private
python3 operations.py verify
```

`SESSION_SECRET` en az 32 rastgele karakter olmalı; örnek yer tutucular kabul edilmez. Caddy güvenilir vekil adresi `172.30.0.2` olarak sabittir. Başka ağdan gelen `X-Forwarded-For` başlıkları API tarafından güvenilir kabul edilmez. Compose ağı bu subnet ile çakışırsa API vekil adresi ve Compose birlikte değiştirilip yeniden test edilir.

## Otomatik maliyet yenileme

Üretimde `GOOGLE_PRICE_AUTO_REFRESH_ENABLED=true` varsayılandır. FastAPI açılışta ve ardından altı saatte bir, kimlik bilgisi göndermeden Google'ın herkese açık fiyat listesini, TCMB kurunu ve gözden geçirilmiş GİB KDV referansını okur. Bu işlem Places, Geocoding veya Routes çağrısı yapmaz. Başarısız güncelleme 15 dakika sonra yeniden denenir; son doğrulanmış kayıt bozulmaz ve doğrulama tarihi başarısızlıkta ilerletilmez. Ayrı Codex otomasyonu veya sunucu yeniden başlatması gerekmez.

Doğrulanmış fiyatlar SQLite dosyasının yanındaki `google-prices.json` dosyasına atomik olarak yazılır. Bütçe kontrolü bu dosyayı yeniden başlatma gerekmeden okur. İlk yükseltmede dosya henüz yoksa süresi geçmemiş ortam değişkenleri kullanılabilir. Var olan dosya bozuksa veya yedi günden uzun süredir doğrulanamıyorsa eski tarih gizlenmez; ücretli arama güvenli biçimde durur. Normal koşullarda altı saatlik yenileme sayesinde kurulum tarihinden yedi gün sonra kendiliğinden kullanım kesilmez.

Hesap, kullanılan SKU'ların ilk ücretli kademesini esas alır; ücretsiz aylık kullanım veya hacim indirimi varsaymaz. Kur rezervi en az 60 TL/USD veya TCMB satış kurunun %20 fazlasıdır; ayrıca %20 KDV rezervi ve %25 güvenlik payı korunur. Bu değerler tahmini rezervdir, fatura veya kesin tahsilat tavanı değildir. GİB referans dosyası değişirse otomatik vergi yorumu yapılmaz; yeni belgenin gözden geçirilmesi gerekir. [Google fiyatları](https://developers.google.com/maps/billing-and-pricing/pricing), [TCMB](https://www.tcmb.gov.tr/kurlar/today.xml), [GİB](https://cdn.gib.gov.tr/api/gibportal-file/file/getFileResources?objectKey=arsiv%2Fyardim-kaynaklar%2Fyararli-bilgiler%2Fkdv-oranlari.pdf).

Yenileme, bütçeyi, API kotalarını, kullanım geçmişini, guard dosyasını veya oturum güvenliğini değiştirmez. Yetkili bir harcama tavanı olmadan sınırsız kullanım açılmaz. Bu özellik ancak testleri geçen yeni API imajı gerçekten sunucuda çalıştırıldıktan sonra canlıya geçmiş sayılır; yalnızca GitHub'a gönderilmesi mevcut sunucuyu güncellemez.

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
