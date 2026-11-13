# ORTAK Mobil: Yayın ve Uyumluluk Kontrolü

Kontrol tarihi: 12 Kasım 2026. Bu belge teslim kontrolüdür; mağaza onayı veya
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
| Bekliyor | Mobil API'nin Oracle'a kontrollü yüklenmesi | `/mobile/session`, `/mobile/feedback`, mevcut web regresyonu; eski imaja geri dönüş |
| Bekliyor | Mobil gizlilik sayfasının yayımlanması | `mobile-privacy.html` ve `mobile-terms.html` herkese açık HTTPS 200 |
| Bekliyor | Apple Developer ve Play Console sahipliği | Kullanıcının kimlik/kurum doğrulaması, imzalama; ücretli kayıt otomatik yapılmaz |
| Bekliyor | EAS projesi veya yerel derleme ortamı | Apple takım/provisioning, Android upload key; hiçbir anahtar Git'e girmez |
| Bekliyor | Gerçek iPhone, iPad, Android testleri | İzin verilmesi/reddi, yaklaşık konum, ayarlar dönüşü, süreç sonlandırma, TTL, paylaşım, ekran okuyucu, büyük yazı, rotasyon |
| Bekliyor | Yerel ikili paket doğrulaması | İmzalı IPA/AAB; 16 KB Android testi, native crash, nihai izin listesi ve Privacy Report |
| Bekliyor | Gerçek mobil uçtan uca kabul | Cihazda Llama önizleme/onay ve tam Google matrisi; kayıtlı harcama onayı/kota korunarak ayrı test |
| Bekliyor | Mağaza metaverileri | Gerçek ekran görüntüleri, destek iletişimi, yaş derecelendirme, hedef kitle, veri beyanları, erişim yönergeleri |
| Hesaba bağlı | Google kapalı test | Yeni kişisel hesaplarda en az 12 testçi, kesintisiz 14 günlük katılım; ardından üretim erişimi başvurusu [1] |
| Bekliyor | TestFlight ve mağaza incelemesi | İnsan incelemesi; bu kodun derlenmesi tek başına kabul anlamına gelmez |

Canlı web sitesinin erişilebilir olması mobil uçların yüklendiği veya mağaza
sürümünün hazır olduğu anlamına gelmez. Bu turda üretim yapılandırması, harcama
sınırları ve canlı veritabanı değiştirilmedi. Silinmiş otomasyon geri kurulmadı.

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
