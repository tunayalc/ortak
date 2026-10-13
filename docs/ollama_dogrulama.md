# Ollama Entegrasyonu: Doğrulama Kaydı

## Llama 3 8B Geçişi

26 Eylül 2026'da `llama3:8b` kuruldu ve ORTAK'ın varsayılan modeli yapıldı. Ollama model listesi ve `/health` yanıtı modelin kurulu ve hazır olduğunu doğruladı. Mevcut 12 kurgusal Türkçe örnek, Llama 3 ile birer kez çalıştırıldı: ilk deneme **9/12**, küçük doğrulama düzeltmesinden sonraki son deneme **12/12**. İlk kayıttaki üç hata fiyat, genel yakınlık ve mevcut ayarları koruma isteklerindeydi. Llama 3'ün dayanak ifadesindeki bir sözcüğü çevirmesi ve genel yakınlığı belirli bir kişiye bağlaması nedeniyle öneriler güvenli biçimde reddedilmişti. Son doğrulama, küçük yazım farkını yalnızca metinde aynı kriterin dayanağı varsa kabul eder; genel yakınlık ifadesini kişi ağırlığına dönüştürmez.

Son yerel canlı kayıt: `output/ollama/llama3-final.json`; ilk başarısız kayıt: `output/ollama/llama3-evaluation.json`. 26 Eylül doğrulamasında **78 backend testi** ve frontend derlemesi geçti. Bu 12 cümle geliştirme setidir; genel Türkçe başarısı ölçümü değildir. Aşağıdaki üç tekrarlı Qwen sonuçları önceki modelin tarihsel kaydıdır. Özel çalışma kayıtları açık kaynak depoya eklenmez.

## Yayın Kabulü

13 Ekim 2026'nın ilk üretim hazırlığında 124 backend ve 14 arayüz testi geçmişti; bu tarihsel sonuçlar sunucu model doğrulaması değildi. Sonrasında Oracle'daki gerçek `llama3:8b`, 12 kurgusal Türkçe senaryoyu üçer kez çalıştırarak **36/36** kabulü geçti. İlk soğuk deneyde 120 saniyeyi aşan tek istek vardı; başarısız rapor korundu. Açılışta model yüklemesinden sonraki kabulde en uzun yanıt 51,756 saniye ve bellek taşması yoktu.

14 Ekim'de gerçek üretim HTTPS tarayıcısında fiyat önceliği ve 2/1/1 kişi ağırlığı isteği 20,972 saniyede yorumlandı. Onay öncesinde ayarlar değişmedi; onaydan sonra üç gerçek Google mekânı ve dokuz rota ile öneriler üretildi. Profil/kişi/filtre güncellemeleri ek Google çağrısı üretmedi. Son CI sonucu **167 backend ve 34 arayüz testi**; bu otomatik testler gerçek model kabulünden ayrı tutulur. Klavye testindeki seçici hatası sıfır ücretli çağrılı canlı kontrolle düzeltildi; özgün başarısız kayıt silinmedi. Yerel ve üretim deneyleri genel Türkçe doğruluk garantisi değildir. Tam yayın kabulü için 24 saatlik sağlık gözlemi hâlâ gereklidir. Güncel ayrıntılar [yayın kılavuzundadır](yayin_kilavuzu.md).

## Önceki Qwen Doğrulaması

## Ortam

- Tarih: 26 Eylül 2026, Türkiye saati.
- O zamanki model: yerelde önceden kurulu `qwen2.5:3b`, 3,1B, Q4_K_M.
- Ollama: `0.33.3`; makine: Apple Silicon, 16 GB bellek.
- Yeni model indirilmedi, model eğitilmedi, OpenAI çağrısı yapılmadı.
- Yerel uç nokta: `http://127.0.0.1:11434/api/chat`; `stream=false`, `temperature=0`.

## Canlı Sonuçlar

Testler kurgusal Ayşe/Bora etiketlerini kullanır; modele `Kişi 1`/`Kişi 2` gönderilir. Beklentiler senaryo bazında kontrol edilir: doğru kriterin etkisinin artması, diğer ayarların korunması, doğru kişi ve sayısal sınırlar, gerekli belirsizlik/bütçe uyarıları. Modelin açıklama cümlesi başarı ölçütü olarak kullanılmaz.

| Senaryo | Başarılı tekrar |
| --- | ---: |
| Mekân puanı önceliği | 3/3 |
| Fiyat uygunluğu önceliği | 3/3 |
| Genel yakınlık önceliği | 3/3 |
| Bir kişiye 2x yakınlık ağırlığı | 3/3 |
| Farklı kişi ağırlıklarını eşitleme | 3/3 |
| Asgari 4 puan | 3/3 |
| Azami 20 dakika, Türkçe ekli ifade | 3/3 |
| “Bana yakın olsun” belirsizliği | 3/3 |
| TL bütçesi ve fiyat önceliği | 3/3 |
| Yazım hatalı fiyat isteği | 3/3 |
| Fiyat + kişi deltası + puan sınırı | 3/3 |
| Önceden ayarlanmış değerleri koruma | 3/3 |

Toplam **36/36**. Bu ölçüm LLM ile backend doğrulamasının birleşik sonucudur, ham model doğruluğu değildir. Servis katmanı yanıt süresi ortalama **1,01 saniye**, ortanca **0,92 saniye**, aralık **0,74-2,25 saniye**. Model önceden yüklenmişti; soğuk başlangıç veya genel performans garantisi değildir.

Makine tarafından okunabilir kayıt: `output/ollama/verified-evaluation.json`. Model özeti, sürüm, kontrol sonuçları ve her isteğin süresi bu dosyada bulunur. Tekrar çalıştırma:

```bash
cd backend
OLLAMA_MODEL=qwen2.5:3b .venv/bin/python scripts/evaluate_preferences.py --output ../output/ollama/qwen2.5-evaluation.json --repeats 3
```

## Bulunan Hatalar ve Düzeltmeler

İlk tam-ayar çıkarma yöntemi 3/12, daha kısa yönerge 4/12, ilk değişiklik çıkarma yöntemi 8/12 geçti. Bunlar sırasıyla `initial-evaluation.json`, `revised-evaluation.json`, `grounded-evaluation.json` kayıtlarında bulunur. Son korumalar öncesindeki üç tekrarlı çalışma 30/36 idi (`final-evaluation.json`); nihai kayıt **verified-evaluation.json** dosyasıdır. Başarısız denemeler silinmedi.

Küçük model bazen kişi deltası ile genel yakınlığı veya fiyat ile puan kriterini karıştırdı. Ollama adaptörü artık tüm ayarları yeniden üretmez; yalnızca istenen değişiklikleri, kişi kimliğini ve kullanıcı cümlesinden tam dayanak ifadesini çıkarır. Backend, alıntının gerçekten istekte bulunmasını, kişi eşleşmesini, sınırları ve çelişkileri kontrol eder. Dayanak ifadesinde tek bir açık kriter sözcüğü varsa yanlış kriter etiketi bu sözcükle çapraz kontrol edilir. Belirsiz “bana” ifadesinde kişi tahmini uygulanmaz. Bunlar deterministik doğrulama kurallarıdır, öğrenilmiş model başarısı olarak sayılmamalıdır.

“20 dakikayı aşmasın” örneğinde doğrulamanın Türkçe eki reddettiği hata düzeltildi. Modelin serbest açıklamalarındaki gerçek yakınlık/mesafe vaatleri kaldırıldı; arayüz açıklaması doğrulanmış ayarlardan üretilir. 2x kişi ağırlığı, gerçek mesafenin yarıya ineceği anlamına gelmez.

## Uygulama Kontrolleri

- 76 backend testi ve `npm run build` geçti. Sağlayıcı seçimi, JSON/şema hataları, kişi kimlikleri, geçersiz sayılar, kesinti, zaman aşımı, metadata ve buluta geçiş yapılmaması test edildi.
- Gerçek Ollama yanıtı tarayıcıda önizlendi. Onay öncesi kriterler `34/33/33`, kişi ağırlığı `1` kaldı.
- Beş kişilik etkin sentetik senaryoda onay sonrası API isteği `34/70/33`, birinci kişi `2`, diğer kişiler `1`, asgari puan `4` içerdi. Öneri API'si 200 döndü ve sonuç kartları güncellendi.
- Açık/koyu tema ile masaüstü (1200 ve 1440 piksel) ve mobil (390 piksel) yerleşim kontrol edildi. Mobil sayfa genişliği 390, masaüstü sayfa genişliği 1440 piksel olarak doğrulandı; yatay taşma yok. Tarayıcı konsolunda hata veya uyarı bulunmadı. Ekran görüntüleri `output/playwright/` altındadır.

## Sınırlar

Bu 12 cümle geliştirme sırasında kullanılan dar bir settir; bağımsız test kümesi veya genel Türkçe anlama başarısı iddiası değildir. Yeni ifadelerde hata olabilir. Kullanıcı önizlemesi ve onayı zorunlu kalır. Sağlık durumundaki “Hazır”, Ollama'nın erişilebilir ve modelin kurulu olduğunu ifade eder, anlamsal doğruluk garantisi vermez.

Uygulama gerçek tercih metinlerini dosyaya/SQLite'a kaydetmez. Değerlendirme betiği yalnızca kaynak kodda tanımlı kurgusal testler için rapor yazar. OpenAI isteğe bağlıdır ve canlı denenmemiştir. Google Maps/OSRM servisleri yerel LLM'den bağımsız harici bağlantılardır.
