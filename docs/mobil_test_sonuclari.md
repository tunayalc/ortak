# ORTAK Mobil İlk Sürüm: Doğrulama Kaydı

Tarih: 13 Kasım 2026. Sürüm: `mobile/0.1.0`, yerel çalışma ağacı.
Bu kayıt mağaza kabulü veya canlı mobil uçtan uca başarı belgesi değildir.

## 13 Kasım: İki Ayrı Motor

- Mekân bul ve Buluşma Planı ayrı ekranlara ve bellekte ayrı durumlara sahiptir.
  Plan önerisi gerçek mekân veya rezervasyon gibi sunulmaz. Kullanıcı isterse
  onay penceresinden ORTAK'a boş kişi konumlarıyla yeni bir arama taslağı aktarır;
  bu adım Google çağrısı başlatmaz.
- 319 backend, 42 web arayüzü ve 9 gateway/aktarım testi başarılıdır. Web testleri
  390 ve 1440 pikselde iki temayı, önizleme onayını, iptal/onay aktarımını ve
  eski arama akışlarını kapsar. Önceki çalışmada bir test, yerel disk alanı
  hatasıyla kesildi; son tam çalışmada 42/42 başarı doğrulandı.
- Mobilde 25 test, TypeScript kontrolü ve iOS/Android/web export başarılıdır.
  Bunlar üretim imzalı IPA/AAB veya fiziksel cihaz kabulü değildir.
- Gerçek yerel `llama3:8b` ile beş plan yorumlama senaryosunun tamamı geçti;
  yanıt süreleri yaklaşık 3,6-5 saniyeydi. İlk denemedeki iki yorumlama hatası
  sonrasında istem düzeltildi; ilk başarısız kayıt özel arşivde korundu.
  Son testte Google çağrısı yapılmadı ve Oracle performansı ölçülmedi.
- Mobil web önizlemesinde plan oluşturma, aktarımı iptal etme, isteğe bağlı
  aktarım, kişi konumlarının boş kalması ve planın korunması ayrıca kontrol
  edildi. Native iOS/Android mağaza yayını ve üretim API kabulü hâlâ gereklidir.

## 12 Kasım: Son Teknik Hazırlık Kontrolü

- Backend testleri yeniden çalıştırıldı: **286 geçti**. Vercel yayın dosyaları
  için 11 ek izin listesi testi, özel yapılandırma ve çıktıların yayımlanmasını
  reddettiğini doğrular.
- Gateway testleri: **6 geçti**. Yeni alan adları kabul edilirken sahte alt alan
  adları, HTTP ve farklı kaynaklı değişiklik istekleri reddedilir.
- Mobil: **23 test**, TypeScript ve native yapılandırma kontrolü başarılıdır.
  Bağımlılık denetimi açık bildirmedi; iOS/Android/web export tamamlandı.
- Web üretim derlemesi başarılıdır. **129** izinli kaynak dosyasında gizli bilgi
  taraması uyarı üretmedi. Bu tarama mutlak güvenlik garantisi değildir.
- Gateway test adımı GitHub CI dosyasına eklendi; bu son yerel değişiklikler
  henüz gönderilmedi, dolayısıyla uzak CI başarısı olarak gösterilmez.
- Bu kontrolde Google'a ücretli istek, Llama üretimi, mobil paket imzalama veya
  mağaza gönderimi yapılmadı. Canlı sunucu ve harcama kayıtları değiştirilmedi.
- Yerel testler, fiziksel cihaz testi veya mağaza onayı yerine geçmez.

## Tamamlanan Kontroller

| Kontrol | Sonuç | Kapsam |
|---|---|---|
| Backend `pytest -q` | 275 geçti | Mevcut regresyonlar, mobil oturum izolasyonu, süre sonu, imza, kaynak kontrolü, hız koruması, bildirim verisi/TTL |
| Mobil `npm test` | 23 geçti | Ağırlıklar, kişi deltası, öneri önizlemesi, API oturumu, tekrar geocode etmeme, kesik matris, silme, hedef linki ve iki temanın kontrastı |
| Mobil `npm run typecheck` | Başarılı | Sıkı TypeScript kontrolü |
| Expo Doctor | 20/20 | Kaynak konfigürasyonu/CNG projesi; fiziksel cihaz testi değil |
| `npm run check:native` | Başarılı | Ön plan konumu, kapalı arka plan/izleme izinleri, HTTPS, yedek ve uygulama kimliği kontrolleri |
| `npm audit --audit-level=moderate` | 0 açık | Mobil kilit dosyasındaki mevcut bağımlılıklar; kalıcı güvenlik garantisi değil |
| Mobil `npm run export` | Başarılı | iOS/Android Hermes ve web paketleri; imzalı IPA/AAB değil |
| Android `assembleDebug` | Başarılı | ARM64 geliştirme APK'sı; Gradle 9.4.1, Java 17, target API 36, compile API 37 |
| Android release manifest | Başarılı | Arka plan konumu, kamera, mikrofon, reklam kimliği ve ekran üstü gösterim izni yok; yedek kapalı |
| APK `zipalign -c -P 16 4` | Başarılı | ZIP yerleşimi kontrolü; 16 KB cihaz/ELF kabulü yerine geçmez |
| Android 36 emülatörü | Başlangıç geçti | Native form, sekmeler, izin öncesi açıklama, sistem konum penceresi ve izin reddinde manuel giriş |
| Web `npm run build` | Başarılı | Mevcut React/Vite uygulaması ve yeni mobil hukuki sayfalar |
| Web Playwright | 34 geçti | 390 ve 1440 pikselde formlar, kişi deltası, filtreler, tema, klavye ve kota davranışları |
| Playwright mobil web önizlemesi | 35 kontrol geçti | Yerel sahte API yanıtları; gerçek Google/LLM çağrısı yapılmadı |
| Açık kaynak dosya taraması | Sorun bulunmadı | Yeni mobil kaynaklar ve izlenen dosyalar; özel çıktı/anahtarlar yayın kapsamı dışında |

## Arayüz Kabulü

`mobile/tests/ui-smoke.cjs`, yerel Expo önizlemesini Playwright üzerinden
sınar. Tekrarlı çağrılar dahil 35 doğrulama; bunlar 35 bağımsız native cihaz testi
olarak yorumlanmamalıdır.

- Hatalı konum yeni senaryo oluşturmaz; geçerli koordinat ikinci geocode'a gitmez.
- Llama önizlemesi onaydan önce ağırlıkları değiştirmez; onayda `2/1/1` uygulanır.
- Sorun bildirimi uygulama içinden gönderilir; metin ve kişi konumu eklenmez.
- Eksik rota matrisi öneri olarak sunulmaz; tekrar aynı senaryo/adayları kullanır.
- Profil, kişi dengesi ve filtre değişiklikleri yeni rota çağrısı üretmez.
- Bilinmeyen fiyat, boş sonuç, kota, bağlantı kesintisi ve başarısız silme açıkça gösterilir.
- Başarısız yeniden sıralama otomatik tekrar döngüsü oluşturmaz.
- Sekme/profil/onay durumları erişilebilirlik ağacına yansır; klavyeyle sekme seçilir.
- 390x844, 844x390, 1024x1366 ve 1440x900 ekranlarda açık/koyu tema kontrol edilir.
- Kontrol edilen düğme, alan, sekme ve başlıklar yatay taşma üretmez.
- Başlıktaki tema düğmesi ve sistem görünümüne geri dönüş doğrulanır.
- Normal metin/zemin çiftleri en az 4,5:1, giriş alanı sınırları en az 3:1 kontrast sağlar.

Görsel kanıtlar özel `output/playwright/mobile-*-light.png` ve
`output/playwright/mobile-*-dark.png` dosyalarıdır. Ekranlardaki mekânlar test
verisidir; bunlar mağaza ekran görüntüsü veya canlı Google kanıtı değildir.

## Henüz Doğrulanmayanlar

- iOS native derleme: bu bilgisayarda Xcode ve CocoaPods bulunmuyor.
- Android üretim imzalı AAB ve tüm hedef mimariler. Oluşturulan debug APK Metro
  geliştirme sunucusu ister; bağımsız mağaza paketi değildir.
- Fiziksel iPhone/iPad/Android, konum izinleri, yaklaşık konum, ekran okuyucu,
  büyük metin, süreç sonlandırma, native paylaşım ve 16 KB sayfa boyutu.
- Mobil API'nin üretime yüklenmesi, gerçek cihazdan gerçek Llama/Google kabulü.
- Apple Privacy Report, Play Data safety, imzalı IPA/AAB, TestFlight/Play testleri.
- GitHub Actions dosyası hazırlandı, ancak bu yerel değişiklikler gönderilmedi;
  uzak CI veya mağaza gönderimi başarılı olarak raporlanmıyor.

Üretim sunucusu, kullanım sayacı ve bütçe değişmedi. Ücretli bulut derlemesi,
Google API testi, mağaza üyeliği veya ödeme başlatılmadı.

Android emülatörü yerel API'ye bağlandı; Google çağrıları ve model üretimi kapalıydı.
Bu native başlangıç testi tam Google rota matrisi kabulü olarak sayılmadı.
Geliştirme APK'sı `output/mobile/ortak-0.1.0-debug.apk` dosyasındadır.
Geliştirme APK'sındaki debug ağ/overlay izinleri üretim izin beyanı değildir;
ayrı `processReleaseMainManifest` çıktısı incelendi. Xcode kurulmadan iOS native
başlangıcı doğrulanmış sayılmaz. Native görsel kanıtlar `output/mobile/` altındadır.

Sıradaki adımlar: [Mobil Yayın Kontrolü](mobil_yayin_kontrolu.md).

## Görsel Dil

[DeFacto web arayüzü](https://www.defacto.com.tr/Login) ve
[resmî Android uygulama görselleri](https://play.google.com/store/apps/details?id=com.defacto.android)
12 Kasım 2026 tarihinde referans olarak incelendi. Düz koyu/açık düğmeler,
ince ayırıcılar, küçük köşe yarıçapları ve sade sans-serif tipografi ORTAK'a
uyarlandı. Marka, simge ve içerik ORTAK'a aittir; DeFacto logosu, fotoğrafları
ve özel font dosyaları uygulamaya alınmadı. Koyu görünüm ORTAK için hazırlanan
bir uyarlamadır; DeFacto'nun doğrulanmış koyu temasının kopyası olduğu iddia edilmez.

Web ve mobil önizleme Codex'in uygulama içi tarayıcısında açıldı. Tema
değişiklikleri henüz Vercel/Oracle'a veya uygulama mağazalarına gönderilmedi.
