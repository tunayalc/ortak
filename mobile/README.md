# ORTAK Mobil

React Native / Expo 58 ve TypeScript ile iOS, iPadOS ve Android istemcisi.
Bu klasör mağazada yayımlanmış bir uygulama değildir. Mevcut web sitesi ve canlı
sunucu bu geliştirme turunda değiştirilmedi. Mağaza kabulü garanti edilmez.

## Kurulum

Node 24.15 veya Expo'nun desteklediği Node 22.13+ sürümü gerekir.

```sh
cd mobile
npm ci
npm run typecheck
npm test
npm run doctor
npm run check:native
npm run export
```

`export`, iOS/Android JavaScript ve Hermes paketleri ile web önizlemesini üretir;
imzalı IPA veya AAB oluşturmaz. `expo prebuild --no-install` yerel projeleri
üretir; `ios/` ve `android/` kaynak konfigürasyondan tekrar üretildiği için
Git'e eklenmez. Yerel native derleme için Xcode veya Android SDK gerekir.

## Yerel Önizleme

Bir terminalde depo kökünden, yalnızca test veritabanıyla:

```sh
APP_ENVIRONMENT=development \
DATABASE_URL=sqlite:////tmp/ortak-mobile-development.db \
GOOGLE_MAPS_API_KEY= GOOGLE_MAPS_CALLS_ENABLED=false \
GOOGLE_PRICE_AUTO_REFRESH_ENABLED=false LLM_PROVIDER=disabled \
ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081 \
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend \
  --host 127.0.0.1 --port 8013 --no-access-log
```

Diğer terminalde:

```sh
cd mobile
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8013 npm run web -- --host localhost --port 8081
```

Önizleme: <http://localhost:8081>. Bu güvenli geliştirme ayarında Google/LLM
üretimi kapalıdır; gerçek mekân sonucu üretmez. Loopback HTTP yalnızca geliştirme
paketinde kabul edilir. Telefon için loopback adresi bilgisayarı göstermez:
gerçek cihazda mobil API güncellemesi yapılmış HTTPS sunucusu kullanılmalıdır.

## Mobil API

İstemci varsayılan olarak Oracle HTTPS `/api` adresini kullanır; Vercel web
geçidini veya web çerezini kullanmaz. `EXPO_PUBLIC_API_BASE_URL` yalnızca açık
sunucu adresidir; buraya API anahtarı veya gizli bilgi konmaz.

`POST /mobile/session` iki saatlik imzalı bir bearer anahtarı verir.
Anahtar, konumlar, ham linkler ve tercih metni yalnızca RAM'dedir. Süre bitince
istemci yerel kişisel veriyi temizler. Mutasyonlar otomatik tekrar edilmez.
Web cookie/CSRF akışı değişmemiştir; mobil oturumlar ayrı imzalama salt'ı kullanır.
Sunucuya bu kod yüklenmeden mobil bağlantının çalıştığı iddia edilmemelidir.

Model çıktısı önce önizlemedir; kullanıcı onaylamadan ağırlıkları değiştirmez.
Kişi konumu alanları modele gönderilmez. Tercih metnine kişisel bilgi eklenmemelidir.
Kriter/kişi değişimleri mevcut matristen yeniden sıralama yapar. Başarılı parse
koordinatları `/scenarios` isteğinde kullanılır; aynı link tekrar geocode edilmez.
Eksik matris tamamlanmadan sonuç gösterilmez. Paylaşılan link yalnızca hedef içerir.

`POST /mobile/feedback`, öneri hakkında kategorik bildirim alır. Yalnızca sorun
türü, kriter ağırlıkları, rastgele bildirim kimliği ve zaman saklanır. Ham metin,
kişi etiketi, oturum kimliği ve konum saklanmaz. Kayıtlar 30 gün sonra temizlenir.
Yetkili işletmeci bunları haftalık incelemeli; bu akış kendiliğinden e-posta göndermez.

## Test ve Paketleme

`tests/ui-smoke.cjs`, Playwright CLI `run-code --filename` ile yukarıdaki yerel
önizleme üzerinde çalışır. Tüm API yanıtları testte taklit edilir, üretim Google
ve Llama doğrulaması değildir. Ekran görüntüleri `output/playwright/` altındadır.
Kişisel içerik, token ve canlı Google yanıtı test raporuna alınmamalıdır.

`eas.json` içindeki preview APK, iOS simulator ve production AAB/IPA profilleri
hazırdır. EAS projesi, Apple/Google mağaza hesabı ve imza anahtarları henüz
bağlanmadı. Otomatik mağaza gönderimi yoktur; EAS kullanımı veya mağaza üyeliği
kendiliğinden başlatılmaz. `com.tunayalc.ortak` ilk mağaza kaydından önce hesap
sahibince doğrulanmalıdır; yayımlandıktan sonra paket kimliği değiştirilemez.

Sürüm engelleri ve veri beyanı: [Mobil Yayın Kontrolü](../docs/mobil_yayin_kontrolu.md).
Yerel doğrulama ve test sınırları: [Test Sonuçları](../docs/mobil_test_sonuclari.md).

## Varlıklar ve Bağımlılıklar

ORTAK ikonları mevcut `frontend/public/favicon.svg` kaynağından
`npm run assets` ile üretilir. Google Maps logoları değiştirilmeden resmi
[atıf paketinden](https://developers.google.com/static/maps/documentation/images/Google_Maps_Attribution_Assets.zip)
alındı; Google markası MIT lisansının kapsamına girmez.

Expo fingerprint'in `minimatch` bağımlılığı GHSA-g3hv-75wg-m249 nedeniyle
11.0.1'e sınırlandı. Config introspection, doctor ve platform export bu sürümle
test edilmelidir; Expo düzeltmesi geldikten sonra override yeniden değerlendirilmelidir.
