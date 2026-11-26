# ORTAK Mobil: Yayın ve Uyumluluk Kontrolü

Kontrol tarihi: 25 Kasım 2026. Bu belge teslim kontrolüdür; mağaza onayı veya
hukuki uygunluk garantisi değildir. Kurallar başvuru gününde yeniden kontrol edilir.

## Tamamlanan İlk Dilim

- Expo 58 / React Native / TypeScript ile bağımsız yerel istemci, WebView değil.
- Buluşma, Tercihler, Öneriler ve Gizlilik ekranları; açık/koyu/sistem teması.
- Link/koordinat, isteğe bağlı tek seferlik cihaz konumu; arka plan takibi yok.
- Puan, fiyat, yakınlık ve kişi deltaları; dengeli kişiler; skor açıklaması.
- Llama önerisini inceleyip uygulama; manuel kullanım modelden bağımsız.
- Google atıfları; yalnızca hedef içeren yol tarifi ve sistem paylaşımı.
- İki saatlik, RAM'de tutulan mobil oturum; senaryo silme; web izolasyonu korunuyor.
- İzin öncesi açıklama, veri paylaşımı onayı, uygulama içi AI sorun bildirimi.
- Native yapılandırma, ikonlar, EAS profilleri ve CI doğrulamaları hazırlandı.

## Yayından Önce Kapatılacaklar

| Durum | İş | Kanıt / Kabul |
|---|---|---|
| Kısmen doğrulandı | Mobil API'nin Oracle'a kontrollü yüklenmesi | `51b1934` canlı; `/runtime-config` mekân türü ve kişi bazlı ulaşım yeteneklerini bildiriyor. Gerçek cihazdan bildirim ve öneri akışı bekliyor |
| Tamamlandı | Mobil gizlilik ve kullanım koşulları | `https://ortak.web.tr/mobile-privacy.html` ve `https://ortak.web.tr/mobile-terms.html` herkese açık HTTPS 200 |
| Kısmen doğrulandı | Apple Developer ve Play Console doğrulamaları | Apple Developer aktif, `com.tunayalc.ortak` kayıtlı. Play kimlik onaylı; gerçek Android cihaz ve telefon doğrulamaları bekliyor, uygulama oluşturma kapalı |
| Tamamlandı | Mağaza imzalama | Android yükleme anahtarı ve Apple Distribution özel anahtarı yerelde. iOS `0.4.1 (6)` Xcode'daki hesapla otomatik imzalandı (Xcode yönetimli App Store profili). Android `0.4.1 (6)` imzasız AAB hazır; `output/mobile/next-0.4.1-6/sign-aab.sh` şifreyi Terminal'de sorarak yükleme anahtarıyla imzalar |
| Bekliyor | Gerçek iPhone, iPad, Android testleri | İzin verilmesi/reddi, yaklaşık konum, ayarlar dönüşü, süreç sonlandırma, TTL, paylaşım, ekran okuyucu, büyük yazı, rotasyon |
| Tamamlandı | iOS simülatör açılışı | iPhone 18 Pro ve iPad Pro 13 inç (M5) üzerinde `0.1.0 (1)` açıldı. `output/mobile/app-store/` altındaki iki görsel App Store Connect'e yüklendi |
| Tamamlandı | Android yerel açılış ve ana akış | API 36 ARM64 emülatörde dağıtım AAB'sinden üretilen test APK'sı açıldı. İki motorun ekranları yakalandı. Canlı mobil API'de oturum, Google arama kapasitesi ve ücretsiz plan isteği doğrulandı; bu mobil kontrolde Google çağrısı yapılmadı |
| Tamamlandı | Yerel paket imza doğrulaması | Android AAB `bundletool` doğrulamasından geçti; API 36 ve 16 KB hizalama korundu. iOS `0.1.0 (1)` App Store IPA'sında `codesign --verify --deep --strict` ve paket kimliği doğrulandı |
| Bekliyor | Gerçek mobil uçtan uca kabul | Cihazda Llama önizleme/onay ve tam Google matrisi; kayıtlı harcama onayı/kota korunarak ayrı test |
| Kısmen tamamlandı | Mağaza metaverileri | Apple metinleri, `13+` yaş derecelendirmesi, gizlilik, içerik hakları ve görseller kayıtlı. Play metni, ikon, tanıtım görseli ve iki güncel Android ekranı `output/mobile/google-play/` altında; yükleme hesap doğrulamasını bekliyor |
| Hesaba bağlı | Google kapalı test | Yeni kişisel hesaplarda en az 12 testçi, kesintisiz 14 günlük katılım; ardından üretim erişimi başvurusu [1] |
| Yayında / incelemede | App Store | iOS `0.1.0 (1)` 23 Kasım 2026'dan beri Türkiye App Store'da yayında. `0.3.0 (3)` 25 Kasım'da onaylandı (`Ready for Distribution`, otomatik yayın). `0.4.0 (5)` (odalar, yer adıyla arama, Deniz teması, yeni simge) onaylanıp yayına çıktı. `0.4.1 (6)` (üyeler kendi yerini girer, yönetici yalnızca ağırlık seçer, kırmızı-beyaz tema, sade arayüz) 27 Kasım'da incelemeye gönderildi; yenilik ve inceleme notları 0.4.1'e göre güncellendi. TestFlight'ta `ORTAK iPhone QA` iç grubunda. Hazır React Native çatılarının dSYM uyarısı için `mobile/scripts/add-prebuilt-dsyms.sh` eklendi; `0.3.0` arşivinde semboller yerelde tamam |

Yayımlama paketleri `output/mobile/` altında ve Git dışında tutulur.
`ortak-android-0.1.0-upload-ready.aab` yükleme anahtarıyla imzalıdır.
`ORTAK-iOS-0.1.0-1.ipa` imzalı App Store paketidir.
`ORTAK-0.1.0-unsigned.xcarchive` kaynak Xcode arşividir.
`output/mobile/ios-0.4.1-6/` iOS `0.4.1 (6)` arşivini, `output/mobile/next-0.4.1-6/` Android `0.4.1 (6)` paketini ve imzalama betiğini içerir. Önceki sürümlerin çıktıları kendi klasörlerinde durur.
Android paketi yüklenmedi. Canlı web ve mobil API
doğrulamaları mağaza yayını veya fiziksel cihaz kabulü yerine geçmez. Satıcı beyanı ekranı
geliştirici e-postasının, yasal ad ve adresin ve geliştirici telefonunun herkese
açık gösterileceğini bildirir; hesap sahibinin bu alanları incelemesi gerekir.

## Veri Envanteri ve Beyan Taslağı

Verilerin RAM'de olması, cihaz dışına aktarımın olmadığı anlamına gelmez.
İki saatlik buluşma saklama süresi için kendiliğinden "yalnızca anlık işleme" veya
"hiç veri toplamıyoruz" beyanı kullanılmaz. Google formu ve Apple Privacy Report,
nihai ikili paket ile gerçek veri akışı karşılaştırılarak tamamlanır. [2][3]

| Veri | Amaç / alıcı | Saklama / silme |
|---|---|---|
| Katılımcı etiketi, isteğe bağlı gerçek ad | Buluşma; Oracle backend | Senaryo belleği, en geç iki saat; kullanıcı silmesi |
| Hassas/yaklaşık koordinat, harita linki | Mekân/rota; backend, Google Maps | Ham link kalıcı yazılmaz; konum/sonuç oturumu en geç iki saat; Google'ın politikası ayrıca geçerli |
| Tercih metni | Sunucudaki Ollama Llama | İstek işlenirken RAM; ham metin günlük/veritabanına yazılmaz; serbest alana kişisel bilgi yazılmaması belirtilir |
| Rastgele oturum kimliği, günlük IP özeti | Oturum ayrımı ve kötüye kullanım engeli | Cihazda RAM; sunucuda süreli hız kayıtları; altyapının erişim kayıtları ayrıca incelenir |
| İşlem türü, durum, süre ve maliyet | Harcama ve işletim kaydı | İçeriksiz kalıcı sayaç; konum veya tercih eklenmez |
| AI bildirim kategorisi ve kriter ağırlığı | Hatalı öneriyi değerlendirme | 30 gün; ham metin, ad, konum, oturum/IP kimliği yok |
| Kayıtlı oda adı, üye adları ve ulaşım tercihleri | Sık buluşan grubun aynı bağlantıyı yeniden kullanması; Oracle backend | Konum, oy ve sonuç yok; 90 gün kullanılmazsa veya "Kaydı sil" ile silinir; bağlantı ve anahtarlar yalnızca hash |
| Yer arama metni | Başlangıç noktasını adla bulma; Google Geocoding | Saklanmaz; istek başına bir Geocoding çağrısı |

Ad, konum, kullanıcı içeriği ve oturum kimliği için ihtiyatlı veri bildirimi
konfigürasyona eklendi. Ad/konum birlikte tutulabildiği için bunlar otomatik
"kullanıcıyla ilişkisiz" işaretlenmedi. SDK manifestleri ve required-reason API
beyanları Xcode arşivinden birleştirilerek doğrulanmalı; `prebuild` bunu kanıtlamaz.
Reklam, ödeme, hesap oluşturma, analitik veya izleme SDK'sı bu sürümde yoktur.
Sonradan eklenirse ATT, hesap silme ve gerekiyorsa mağaza içi ödeme şartları
yeniden değerlendirilir. Yeni bir üyelik sistemi bu sürümün gereği değildir. [3][4]

## Platform Kontrolleri

- Apple: minimum işlevsellik, tamamlanmış içerik, çalışan destek/gizlilik URL'leri
  ve incelemeye açık backend gerekir. Native form, konum, paylaşım ve veri silme
  var; bu özellikler kabul garantisi değildir. iOS 26 SDK / Xcode 26 veya üstü
  gereksinimi başvuru gününde tekrar doğrulanır. [4][5]
- Android: yeni uygulamalar için mevcut hedef en az API 36. Expo üretim ayarının
  nihai AAB manifestinden kontrolü yapılır. Native kütüphaneler için 16 KB
  sayfa boyutu testleri ayrıca gerekir; JavaScript export yeterli değildir. [6][7]
- Konum sadece kullanıcı eylemiyle; yaklaşık konum/izin reddi desteklenir.
  Kamera, mikrofon, rehber, reklam kimliği ve arka plan konum izni kapalıdır.
- Google Maps: logo ve sağlayıcı atıfları sonuçta görünür. Google içeriği yerel
  kalıcı favori/çevrimdışı arşiv yapılmaz. Hizmet koşulları ve gizlilik bağlantıları
  sunulur. Fiyat seviyesi gerçek TL bütçesi veya güvenlik garantisi değildir. [8]
- Llama serbest sohbet yerine doğrulanmış kriter değişikliği üretir. İlgisiz
  metinler doğrudan sonuç içeriği olarak sunulmaz. Bildirimler uygulama içinden
  gönderilebilir; işletmeci haftalık kategorik inceleme ve düzeltme kaydı tutmalıdır. [9]
- Çocuklara özel ürün olarak ilan edilmedi. Yaş hedefi ve mağaza yaş anketi yayıncı
  tarafından kararlaştırılmalı; rastgele yaş etiketi veya DSA tacir statüsü girilmez.

## Yayın Sırası

1. Backend testleri, web regresyonu, mobil typecheck/test/doctor/export ve native
   konfigürasyon kontrolü. CI sonucu olmadan canlı sunucu güncellenmez.
2. Kullanım sayacı, guard ve yapılandırma korunarak API imajı güncellenir.
   `/mobile/session` ücretli çağrı yapmadan kontrol edilir; web oturum testi tekrarlanır.
3. Mobil gizlilik/koşul sayfaları yayımlanır. Kararlı API alan adı kararı verilirse
   TLS ve URL erişimi doğrulanır; yeni alan adı alınmadan uygulama kimliği sabitlenmez.
4. Preview APK / iOS development build ile fiziksel cihaz testleri, ardından
   gerçek Llama ve Google kabulü. Başarısız test ücretli tekrara otomatik dönüşmez.
5. Nihai Privacy Report, Play Data safety, destek bilgisi, içerik derecelendirmesi,
   gerçek ekran görüntüleri ve mağaza inceleme yönergeleri tamamlanır.
6. TestFlight/Play kapalı test, ardından insan onayıyla aşamalı üretim yayını.
   Mağaza hesap ödemesi ve sertifika işlemi kendiliğinden yapılmaz.

## Kaynaklar

1. https://support.google.com/googleplay/android-developer/answer/14151465
2. https://support.google.com/googleplay/android-developer/answer/10787469
3. https://developer.apple.com/app-store/app-privacy-details/
4. https://developer.apple.com/app-store/review/guidelines/
5. https://developer.apple.com/news/upcoming-requirements/
6. https://support.google.com/googleplay/android-developer/answer/11926878
7. https://developer.android.com/guide/practices/page-sizes
8. https://developers.google.com/maps/documentation/places/web-service/policies
9. https://support.google.com/googleplay/android-developer/answer/13985936
