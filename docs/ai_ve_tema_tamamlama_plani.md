# ORTAK: Yapay Zekâ ve Tema Tamamlama Planı

## Hedef

Kullanıcının Türkçe mekân tercihlerini, mevcut kriter bazlı karar modeline uygulanabilecek bir **öneriye** dönüştürmek ve ORTAK arayüzünde İnno Derneği uygulamasının açık/koyu tema dilini kullanmak. Araştırmanın sentetik veri ve açıklanabilir skorlama yapısı korunur.

## İş Paketleri

1. **Veri sözleşmesi ve gizlilik - tamamlandı.** `POST /preferences/interpret` tercih metni, mevcut ağırlıklar ve kişi kimliklerini alır. Konum bağlantısı veya koordinat içeren metin reddedilir; kişi etiketleri dış çağrı öncesinde anonimleştirilir. Ham istek SQLite'a yazılmaz.
2. **Dil modeli bağlantısı - Ollama ile tamamlandı.** Varsayılan sağlayıcı `ollama`, model `llama3:8b` değeridir. JSON Schema ile dayanak ifadeleri içeren değişiklikler çıkarılır, backend bunları mevcut ayarlara birleştirir. Sağlık yanıtı model ve servis durumunu ayırır. OpenAI açıkça seçilmedikçe kullanılmaz; otomatik bulut geçişi yoktur.
3. **Kullanıcı onayı - tamamlandı.** Arayüz Türkçe isteği gönderir; önerilen kriter, kişi yakınlığı ve sayısal filtreleri düzenlenebilir önizlemede gösterir. Kullanıcı onayı olmadan mevcut sıralama değişmez. Onaydan sonra etkin senaryo yeniden puanlanır.
4. **İnno teması - tamamlandı.** Kaynak uygulamanın mor vurgu, yeşil durum ve açık/koyu yüzeyleri CSS değişkenlerine aktarıldı. Tema düğmesi ve yerel tercih kaydı eklendi.
5. **Doğrulama - otomatik ve canlı kontroller.** 13 Ekim üretim hazırlığında 124 backend testi, frontend derlemesi ve 14 mobil/masaüstü arayüz testi geçti. Llama 3'ün önceki yerel 12/12 canlı senaryo sonucu ve Qwen çalışmasının tarihsel 36/36 kaydı `ollama_dogrulama.md` dosyasındadır. Bunlar dar geliştirme setlerine aittir; Oracle sunucusundaki 36/36 kabulü henüz tamamlanmadı.

## Canlı Servis Kabulü

Puan, fiyat ve yakınlık öncelikleri; kişi bazlı `2x`; dengeli kişiler; sayısal puan/süre sınırı; TL bütçesi; belirsiz kişi; yazım hataları ve birleşik istekler Llama 3 ile de denendi. İlk çalışmada 9/12, doğrulama düzeltmesinden sonra 12/12 sonuç alındı. Sistem yalnızca istenen değişiklikleri çıkarma, dayanak ifadesini doğrulama, açık kriter sözcüklerini çapraz kontrol etme ve belirsiz kişi durumunda değerleri koruma yöntemlerini birlikte kullanır. Açıklamalar modelin serbest metninden değil, doğrulanmış ayarlardan üretilir.

2209-A deneyleri sentetik konumlarla ve raporda tanımlanan `lambda` karşılaştırmalarıyla yürütülür. Ürün prototipindeki link girişi ve dil modeli, bu deneylerden ayrı gösterilir. Dil modeli kullanımı proje bütçesine dahil edilecekse başvuru belgesindeki gider gerekçesi ayrıca güncellenmelidir; mevcut PDF'de böyle bir kalem açıkça yazılı değildir.

## Kapsam Sınırı

Bu katman önceden eğitilmiş bir dil modelini kullanır; ORTAK için yeni bir makine öğrenmesi modeli eğitildiği iddia edilmez. Konum alanları model isteğine dahil edilmez, tercih metnine konum yazılmamalıdır. Ham tercihler uygulama tarafından kalıcı kaydedilmez. Yerellik yalnızca Ollama çıkarımı içindir; Google Maps/OSRM çağrıları haricidir. OpenAI seçilirse `store=false` kullanılır ve sağlayıcının veri politikası ayrıca geçerlidir. OpenAI canlı çağrısı bu turda yapılmadı.
