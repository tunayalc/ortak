# ORTAK Rapor Uyum Taslağı

## Kullanıcı Tercihi ve Lambda Mantığı

ORTAK karar modeli, rapordaki "kullanıcı tarafından ayarlanabilir adalet-verim dengesi" iddiasını doğrudan `lambda` parametresiyle uygular. `lambda=0` tamamen verim/min-sum, `lambda=1` tamamen adalet/min-max davranışıdır; ara değerler iki kriter arasında sürekli geçiş sağlar. Kullanıcı herhangi bir ayar yapmadığında sistem dengeli kabul edilen `lambda=0.5` değerini kullanır. Bu metindeki formül, web prototipindeki backend skorlama koduyla aynı standart anlatımdır.

Arayüzdeki tercih profilleri yalnızca lambda ön ayarıdır:

| Profil | Lambda | Davranış |
| --- | ---: | --- |
| Verim | 0.00 | Toplam süreyi azaltır |
| Dengeli | 0.50 | Adalet ve verimi dengeler |
| Adil | 1.00 | En uzun bireysel süreyi azaltır |

## Model Formülü

Model önce kullanıcı kısıtlarını uygular: kategori, ulaşım modu, maksimum kabul edilebilir süre, minimum mekân puanı ve Top-K sayısı. Kısıtları geçen adaylar için erişim matrisi üzerinden aşağıdaki özellikler hesaplanır:

- `t_sum`: grubun toplam yolculuk süresi.
- `t_avg`: grubun ortalama yolculuk süresi.
- `t_max`: en dezavantajlı katılımcının yolculuk süresi.
- `variance`: yolculuk sürelerinin grup içindeki dağılım farkı.

Adalet bileşeni en uzun bireysel süreyi azaltmayı temsil eder:

```text
fairness_norm = 1 - norm(t_max)
```

Verimlilik bileşeni toplam grup süresini azaltmayı temsil eder:

```text
efficiency_norm = 1 - norm(t_sum)
```

Mekân kalitesi bileşeni puan, yorum sayısı ve kategori uygunluğundan oluşur:

```text
quality_norm = 0.50 * rating_norm + 0.30 * review_norm + 0.20 * category_match
```

Nihai skor standart lambda formülüne göre hesaplanır:

```text
S_lambda = lambda * fairness_norm + (1 - lambda) * efficiency_norm
```

Mekân kalitesi ana skora ek ağırlık olarak katılmaz. Kalite bileşeni eşit skor durumlarında tie-breaker ve açıklama bileşeni olarak kullanılır.

## Kişi Konumu ve Gelişmiş Öncelik Katmanı

Web prototipi, sentetik konum üretimine ek olarak kişi sayısı kadar Google Maps linki veya `lat,lng` koordinatı girişini destekler. Bu mod gerçek kişi konumu içerebileceği için `session_only` olarak çalışır; ham linkler, kişi koordinatları, adaylar ve rota metrikleri kalıcı SQLite veritabanına yazılmaz. Backend yeniden başlatıldığında link tabanlı oturum senaryoları silinir.

## Ürün Ekranı: Kriter Bazlı Delta Modeli

Ürün arayüzünde son kullanıcıdan beklenen ana karar, `lambda` gibi akademik bir parametreyi ayarlamak değil; mekân seçimini etkileyen somut kriterleri önem sırasına koymaktır. Bu nedenle ürün ekranında temel skor aşağıdaki kriter bazlı delta modeliyle hesaplanır:

```text
final_score =
  w_rating * rating_norm +
  w_cost * cost_norm +
  w_proximity * proximity_norm
```

Burada `w_rating` mekân puanının, `w_cost` fiyat uygunluğunun, `w_proximity` ise kişilere yakınlığın kullanıcı tarafından verilen ağırlığını temsil eder. Ağırlıklar otomatik normalize edilir. Varsayılan dengeli profilde mekân puanı `%34`, fiyat uygunluğu `%33` ve kişilere yakınlık `%33` olarak başlar.

Kişilere yakınlık kendi içinde ayrıca kişi delta katsayılarıyla hesaplanır:

```text
proximity_norm = sum(person_weight_i * closeness_norm_i)
```

`person_weight_i` değerleri katılımcıların yakınlık deltalarından normalize edilir. Kullanıcı "Kişiler dengeli" seçeneğini kullandığında bütün kişi deltaları `1.0` olur ve tüm katılımcılar yakınlık hesabında eşit etki eder. Bir kişinin deltası `2.0`, diğerinin deltası `1.0` ise ilk kişinin konumsal yakınlığı ikinci kişiye göre iki kat daha fazla önemsenir.

Bu modelde yarıçap, ulaşım türü ve `lambda` ana ürün karar ekranında gösterilmez. Yarıçap ve ulaşım türü backend tarafında güvenli varsayılanlarla çalışır. `lambda` modeli ise rapor uyumu, deney ve karşılaştırma katmanında korunur.

### Doğal Dil Tercih Girişi

Ürün prototipinde isteğe bağlı bir dil modeli katmanı, kullanıcının Türkçe isteğini kriter ağırlıkları, kişi yakınlık ağırlıkları ve açıkça belirtilen sayısal filtreler için **öneriye** dönüştürür. Kullanıcı öneriyi düzenleyip onaylamadıkça skorlama değişmez. Dil modeline kişi konum bağlantıları ve koordinatlar aktarılmaz; kişi etiketleri anonimleştirilir. API anahtarı yoksa bu özellik kapalıdır ve elle kriter seçimi kullanılabilir. Bu katman araştırmanın `lambda` modelinin yerine geçmez ve öğrenilmiş bir kullanıcı tercih modeli olarak sunulmaz.

Varsayılan rapor modu değişmeden kalır. Kullanıcı gelişmiş öncelik katmanını açarsa aşağıdaki ek skor kullanılır:

```text
advanced_score =
  w_report * S_lambda +
  w_quality * quality_norm +
  w_cost * cost_norm +
  w_focus * focus_norm
```

Bu katmanda `w_report` rapor uyumlu lambda skorunu, `w_quality` mekân puanı/yorum/kategori etkisini, `w_cost` fiyat uygunluğunu ve `w_focus` odak yakınlığını temsil eder. Bu akış geriye uyumluluk ve rapor karşılaştırmaları için korunur; ürün ekranındaki ana karar ise kriter bazlı delta modeliyle verilir.

## Kişisel Delta: Süre Etkisi ve Yakınlık Etkisi

Kişisel delta katsayısı, ürün ekranında belirli bir katılımcının konumsal yakınlığının ne kadar önemsenmesi gerektiğini ifade eder. Ana kullanıcı akışında bu katsayı süreyi çarpan bir ceza katsayısı olarak değil, kişi yakınlığı ağırlığı olarak yorumlanır:

- Yakınlık deltası: Her katılımcı için adaylara olan uzaklık ters min-max normalizasyonla `closeness_norm_i` değerine çevrilir. Ardından katılımcı deltaları normalize edilerek `person_weight_i` olur ve `proximity_norm = sum(person_weight_i * closeness_norm_i)` hesaplanır.
- Dengeli kişiler: Kullanıcı "Kişiler dengeli" seçeneğini kullandığında bütün katılımcı deltaları `1.0` olur; böylece her kişi yakınlık hesabında eşit ağırlık alır.
- Geriye uyumlu süre deltası: Eski gelişmiş rapor akışında süre deltası seçeneği korunabilir; ancak ana ürün karar ekranında kullanıcıya gösterilen delta kişi yakınlığı ağırlığıdır.

Bu ayrım, kullanıcının "bu kişiye daha yakın olsun" isteğini rapordaki adalet-verim modeliyle karıştırmadan yönetir. Böylece mekân puanı ve fiyat uygunluğu genel kriterler olarak kalır; kişi deltaları yalnızca yakınlık kriterinin kendi içindeki dağılımını belirler.

## Arayüz Taslağı

Arayüz, son kullanıcının karar verme sürecini hızlandıracak ürün uygulaması biçiminde tasarlanır. İlk ekranda şehir, mekân türü, grup büyüklüğü, Top-K ve kişi konumları yer alır. Kullanıcı Dengeli, Puan Öncelikli, Fiyat Öncelikli veya Yakınlık Öncelikli profillerinden birini seçebilir. İsterse mekân puanı, fiyat uygunluğu ve kişilere yakınlık ağırlıklarını sliderlarla doğrudan düzenleyebilir. Kişi konumu panelinde sentetik konum veya link/koordinat girişi seçilir; kişi satırlarındaki yakınlık deltaları ilgili kişinin yakınlık hesabındaki etkisini belirler.

Öneriler tablo yerine kartlar halinde sunulur. Her kartta mekân adı, puan, fiyat/maliyet bilgisi, kişi yakınlığı etkisi, ortalama süre ve Google Maps yol tarifi bağlantısı bulunur. Etik kapsam gereği yol tarifi bağlantısı yalnızca hedef mekânı içerir; başlangıç konumu Google Maps üzerinde kullanıcı tarafından seçilir. Seçilen mekân için sağ detay panelinde "Neden bu mekân?" açıklaması, puan etkisi, fiyat etkisi, kişi yakınlık katkıları ve fiyat kaynağı gösterilir.

Arayüzde ikincil sekmeler bulunur:

- Öneri özeti: etkin ağırlıklar ve tercih kaynağı.
- Karşılaştır: temel yöntem sonuçları, hedef kontrolleri ve istatistiksel değerlendirme.
- Model detayı: karar sırası ve formül.
- Rapor taslağı: bu metnin uygulama içinde okunabilir özeti.

## Deney Planı

### Yerel Dil Modeli: Ürün Katmanı

Ürün arayüzüne, kullanıcının Türkçe tercihlerini yapılandırılmış ayar önerilerine dönüştüren isteğe bağlı Ollama entegrasyonu eklenmiştir. Varsayılan yerel model `llama3:8b` değeridir. Bu çalışma, önceden eğitilmiş bir modelin entegrasyonudur; yeni bir model eğitimi değildir. Dil modeli mekân sıralamasını veya rota hesabını yapmaz.

Model yalnızca istenen değişiklikleri ve bunların tercih cümlesindeki dayanaklarını çıkarır. Backend şema, kişi kimliği, sayısal sınır ve dayanak kontrollerini yapar; belirtilmeyen ayarları korur. Açık kriter sözcükleriyle çapraz kontrol ve belirsiz kişi isteğinde ağırlıkları koruma kuralları deterministiktir. Kullanıcı önizlemeyi düzenleyip onaylamadan karar parametreleri değiştirilmez. Son sıralama mevcut kriter bazlı delta modeliyle hesaplanır.

Konum alanları dil modeline aktarılmaz, kişi etiketleri takma adlarla değiştirilir ve ham tercihler uygulama tarafından kalıcı kaydedilmez. Ollama adımı yereldir; Google Maps ve OSRM bağlantıları bu yerellik iddiasının dışında kalır. API anahtarı gerektiren OpenAI alternatifi yalnızca açıkça seçildiğinde kullanılır; otomatik bulut geçişi yoktur.

Dil modeli doğrulaması, 2209-A kapsamındaki sentetik rota deneylerinden ayrı raporlanır. Küçük geliştirme setinde LLM ve doğrulama katmanının birlikte elde ettiği 36/36 sonucu genel Türkçe başarısı olarak yorumlanmaz. Ayrıntılar ve başarısız ilk denemeler `docs/ollama_dogrulama.md` dosyasında açıklanmıştır.

### Rota ve Karar Modeli Karşılaştırması

Model, aynı senaryo ve tercih profili altında şu yaklaşımlarla karşılaştırılır:

- Rastgele seçim ortalaması: tek rastgele seçim yerine çoklu tekrar ortalaması.
- Coğrafi merkez: sentetik katılımcı merkezine en yakın aday.
- Minimum-toplam süre: `t_sum` değerini minimize eden aday.
- Minimum-maksimum süre: `t_max` değerini minimize eden aday.

Başarı ölçütleri rapordaki hedeflerle aynı tutulur: maksimum bireysel sürede en az %15 azalma, ortalama süre artışının %5'i aşmaması ve süre varyansında en az %15 düşüş. Wilcoxon işaretli sıralar testi ve Cohen `dz` etki büyüklüğü, eşleşmiş kullanıcı süreleri üzerinden raporlanır.

## Risk ve Mantık Tutarlılığı Notları

- Araştırma deneylerinde gerçek kişi verisi toplanmaz; değerlendirme senaryoları sentetik katılımcı konumlarıyla üretilir. Ürün prototipindeki isteğe bağlı link modu deney veri setine dahil edilmez ve yalnızca oturum belleğinde tutulur.
- Google Places API (New), Geocoding API ve Routes API kullanılabilir. Anahtar yoksa demo verileri kullanılır; canlı Google testi yedek veya sentetik veriyi başarı saymaz.
- Sentetik konumlar merkez çevresinde polar koordinatla üretilir; böylece katılımcılar gerçekçi bir yarıçap içinde dağılır.
- Minimum-toplam temel yöntem `t_avg` yerine `t_sum` ile hesaplanır.
- Rastgele temel yöntem tek seçime bağlı değildir; tekrarlı ortalama ile daha kararlı raporlanır.
- Sağlayıcı değiştiğinde eski rota matrisi otomatik olarak doğru kabul edilmez; sağlayıcı uyumu kontrol edilir.
- Özel koordinatlı kullanıcı listeleri varsayılan olarak reddedilir; yalnızca `synthetic_fixture=true` ile açıkça kurgusal test verisi olarak kabul edilir.
- Link/koordinat modunda gerçek kişi konumları session-only saklanır ve API cache dahil kalıcı yazma yapılmaz.
- Ürün ekranındaki ana karar modeli kriter bazlı deltadır; `lambda` modeli rapor, deney ve geriye uyumlu karşılaştırma katmanında korunur.
- Gelişmiş öncelik katmanı kapalıyken saf `S_lambda` davranışı değişmez.
- Filtreler sonrasında en az üç geçerli alternatif yoksa sistem rapor hedefini karşılamadığı için uyarı verir.
- Mevcut PDF dosyasında eski formül ifadeleri bulunduğu için düzenlenebilir kaynak üzerinden güncelleme yapılmalıdır; ayrıntılı değişiklik listesi `docs/rapor_duzeltme_notlari.md` dosyasındadır.

## Google Maps Canlı Doğrulama ve Kayıt Katmanı

Ürün, yeni Google Cloud projeleriyle uyum için Places API (New) ve Routes API kullanır; Geocoding API şehir veya metin konumlarını çözer. API anahtarının tanımlı olması gerçek bağlantı doğrulaması sayılmaz. Canlı deneyde veri kaynağı, kişi-aday matrisinin tamamlanması, HTTP yanıt süreleri, çağrı sayıları ve model kontrolleri ayrı ayrı doğrulanır. Sentetik veya OSRM sonuçları Google canlı test başarısı yerine kullanılamaz.

Tekrar çalıştırılabilirlik için kurgusal senaryo parametreleri, kodun SHA-256 değeri, UTC tarihleri, kullanıcı tercih ağırlıkları, kontrol sonuçları ve izin verilen place ID referansları kaydedilir. Google Places içeriğini sınırsız SQLite cache'inde veya ham deney dosyalarında saklama varsayımı kaldırılmıştır. Sağlayıcının saklama ve atıf koşulları nedeniyle Google mekân ve rota içeriği aktif senaryo belleğinde kullanılır; gerçek kişi verilerinin oturumluk saklanması korunur. Kapsamlı bilimsel veri arşivi için gerekli sağlayıcı izinleri ayrıca doğrulanmalıdır.

Teknik kayıtlar hizmetin çalıştığını ve nasıl kullanıldığını belgeleyebilir; harcama tutarı ve kabulü için fatura, ödeme belgesi ve proje kapsamına uygunluk ayrıca gereklidir. Küçük duman testinin başarısı, araştırma başarı hedefleri veya kamuya açık yayın hazırlığı olarak raporlanamaz.

Ücret doğurabilecek Google çağrıları varsayılan olarak kapalıdır ve kullanıcı onayından sonra açılır. Günlük yerel istek sınırı ve atomik kullanım sayacı yeniden denemeleri de kapsar; servis yeniden başlatıldığında korunur. Kullanım kaydı yalnızca işlem, tarih, HTTP durumu ve süre içerir. Bu sayaç veritabanına kişi konumu veya Google içerik kaydetmez; Google faturasını parasal olarak durdurduğu ya da başka uygulamaları sınırladığı iddia edilmez. Onaylı test bütçesi teknik kayıtta ayrı tutulur; gerçek gider yalnızca geçerli mali belgelerle belirlenir.

