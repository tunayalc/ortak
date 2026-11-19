# Ollama Entegrasyonu: Doğrulama Kaydı

## 16 Kasım 2026: Yerel Arayüz ve Bağlam Revizyonu

Bu bölüm yerel geliştirme sürümünü anlatır; üretime yayın yapılmadı. İki motorun önizleme/onay akışı ve matematiksel sıralaması korunur. Buluşma planları doğrulanmış etkinlik veya rezervasyon değildir. DeFacto kaynak kodları bu ortamda bulunmadı; kullanıcının sağladığı mühendislik ilkeleri uygulandı, referans proje değişikliği yapılmadı.

- Ortak aşama gezinmesi, durum bildirimi ve koşul düzenleyicisi eklendi. Geç gelen yorumlar yeni form değerlerini ezmez; manuel planlama model yanıtını beklemeden sürebilir. Aktarım isteğe bağlıdır ve Google araması başlatmaz.
- `conditions` sözleşmesi kişi başı/toplam TRY bütçesini, hariç tutulan kategorileri ve desteklenen zorunlu özellikleri ayrı taşır. Kısa takiplerde belirtilmeyen alanlar korunur; yeni konu önceki plan koşullarını sıfırlar. Belirsiz kişi/bütçe ve çelişkili ortam önizlemede açıklama ister.
- Google fiyat seviyesi TL değildir. Bütçe filtresi yalnızca kullanıcı tarafından girilmiş kişi başı TL tutarlarıyla karşılaştırma yapar; bu tutarlar doğrulanmış menü fiyatı sayılmaz. Bilinmeyen fiyat bütçeye uyum kanıtı değildir. Doğrulanamayan zorunlu sessizlik, erişilebilirlik ve alkolsüzlük koşulları sessizce kaldırılmaz.
- Puanı bulunmayan aday nötr puan bileşeni alır. TL maliyetleri ile fiyat seviyeleri tek sayısal ölçekte karşılaştırılmaz; karışık ölçekte fiyat bileşeni nötrdür. Sentetik fiyatlar Google verisi diye etiketlenmez. Yakınlık hâlâ kuş uçuşu mesafeye dayanır; rota süresi değildir.
- Yeni istemciler `/runtime-config` içindeki `conditions_v1` / `plan_context_v1` yeteneklerini denetler. Eski sunucuda koşulları yok sayarak yorumlama veya ücretli arama başlatılmaz. Yayın yapılacaksa backend sözleşmesi önce hazır olmalıdır.

Doğrulama: 337 backend testi, 60 masaüstü/mobil Playwright testi, 27 mobil mantık testi ve 9 geçit testi başarılı; web üretim derlemesi ve mobil TypeScript kontrolü başarılı. Web kontrolleri 390, 768, 844 ve 1440 piksel genişlikleri, yatay telefon, açık/koyu tema, azaltılmış hareket, klavye odağı, oturum bitmesi, geç yanıt, boş sonuç ve rota tekrar kullanımını kapsar. Bunlar fiziksel iOS/Android cihaz kabulünün yerine geçmez.

Gerçek yerel `llama3:8b` ile eski tercih seti son çalıştırmada **12/12**, yeni diyalog seti **16/16** geçti. Yeni setin 15 örneği gerçek model çağrısı, biri yalnızca ekranda sunulan plan sırasını çözen deterministik kontroldür. Üç turlu zincirde önceki gerçek model çıktısı sonraki turun bağlamına aktarıldı. Son çalıştırmada model çağrıları 1,70–6,21 saniyeydi; performans garantisi değildir. Başlangıçtaki yeni set 8/13, eski setin ilk tekrarı 11/12 idi: kişi başı ifadesinde grup sayısının değişmesi, koşulun yanlış alana taşınması ve yazım hatalı kriter dayanağının reddi düzeltildi. Bu geliştirme setleri bağımsız genel Türkçe başarı ölçümü değildir.

Tekrar çalıştırma (mevcut yerel model gerekir; model indirme veya Google çağrısı yapmaz):

```bash
backend/.venv-release/bin/python backend/scripts/evaluate_dialogue.py --live
```

Gerçek Llama önizlemesi uygulama içi tarayıcıda da kontrol edildi; mekân/rota arayüz testlerinde sentetik veri kullanıldı. Ücretli Google pilotu yapılmadı. Üretim backend'inin sağlık yanıtı 200 ve model `llama3:8b` hazırdı; üretim yetenek yanıtında yeni koşul sözleşmesi bulunmuyordu. Bu kontrol üretimde yeni sürümün çalıştığı anlamına gelmez.

Sınırlar: serbest Türkçe her koşulu temsil etmez; desteklenen alanlar şemayla sınırlıdır. Katılımcı çıkarma belirsizse kişi tahmin edilmez, kişi listesi üzerinden düzeltme istenir. Fiyat, sessizlik, erişilebilirlik, müsaitlik ve rezervasyon için ek doğrulanmış veri kaynağı sağlanmış değildir. Gerçek kullanıcı metni/konumu değerlendirme kaydına eklenmedi.

## Llama 3 8B Geçişi

26 Eylül 2026'da `llama3:8b` kuruldu ve ORTAK'ın varsayılan modeli yapıldı. Ollama model listesi ve `/health` yanıtı modelin kurulu ve hazır olduğunu doğruladı. Mevcut 12 kurgusal Türkçe örnek, Llama 3 ile birer kez çalıştırıldı: ilk deneme **9/12**, küçük doğrulama düzeltmesinden sonraki son deneme **12/12**. İlk kayıttaki üç hata fiyat, genel yakınlık ve mevcut ayarları koruma isteklerindeydi. Llama 3'ün dayanak ifadesindeki bir sözcüğü çevirmesi ve genel yakınlığı belirli bir kişiye bağlaması nedeniyle öneriler güvenli biçimde reddedilmişti. Son doğrulama, küçük yazım farkını yalnızca metinde aynı kriterin dayanağı varsa kabul eder; genel yakınlık ifadesini kişi ağırlığına dönüştürmez.

Son yerel canlı kayıt: `output/ollama/llama3-final.json`; ilk başarısız kayıt: `output/ollama/llama3-evaluation.json`. 26 Eylül doğrulamasında **78 backend testi** ve frontend derlemesi geçti. Bu 12 cümle geliştirme setidir; genel Türkçe başarısı ölçümü değildir. Aşağıdaki üç tekrarlı Qwen sonuçları önceki modelin tarihsel kaydıdır. Özel çalışma kayıtları açık kaynak depoya eklenmez.

## Yayın Kabulü

13 Ekim 2026'nın ilk üretim hazırlığında 124 backend ve 14 arayüz testi geçmişti; bu tarihsel sonuçlar sunucu model doğrulaması değildi. Sonrasında Oracle'daki gerçek `llama3:8b`, 12 kurgusal Türkçe senaryoyu üçer kez çalıştırarak **36/36** kabulü geçti. İlk soğuk deneyde 120 saniyeyi aşan tek istek vardı; başarısız rapor korundu. Açılışta model yüklemesinden sonraki kabulde en uzun yanıt 51,756 saniye ve bellek taşması yoktu.

14 Ekim'de gerçek üretim HTTPS tarayıcısında fiyat önceliği ve 2/1/1 kişi ağırlığı isteği 20,972 saniyede yorumlandı. Onay öncesinde ayarlar değişmedi; onaydan sonra üç gerçek Google mekânı ve dokuz rota ile öneriler üretildi. Profil/kişi/filtre güncellemeleri ek Google çağrısı üretmedi. Son CI sonucu **167 backend ve 34 arayüz testi**; bu otomatik testler gerçek model kabulünden ayrı tutulur. Klavye testindeki seçici hatası sıfır ücretli çağrılı canlı kontrolle düzeltildi; özgün başarısız kayıt silinmedi. Yerel ve üretim deneyleri genel Türkçe doğruluk garantisi değildir. Tam yayın kabulü için 24 saatlik sağlık gözlemi hâlâ gereklidir. Güncel ayrıntılar [yayın kılavuzundadır](yayin_kilavuzu.md).

17 Ekim'de sunucunun 24 saatlik gözlemi tamamladığı, modelin hazır olduğu ve yaklaşık 78 saat sağlıklı kaldığı doğrulandı. Google kullanımı açıkken systemd açılış yüklemesini engelleyen kontrol düzeltildi; gerçek açılış birimi Google çağrısı olmadan başarılı çalıştı. Son CI **171 backend ve 34 arayüz testini** geçti. Önceki paragraf 14 Ekim'deki durumu anlatır; 24 saat koşulu artık tamamlanmıştır. Yeni model indirilmedi, modele veya ücretli Google akışına alternatif bir sağlayıcı eklenmedi.

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
