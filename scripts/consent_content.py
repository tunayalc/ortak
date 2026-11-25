"""First-launch notice shown on web and mobile. Edit here, then run scripts/sync_catalog.py.

Change VERSION whenever the meaning of a section changes so everyone is asked again.
Statements here must match frontend/public/privacy.html and mobile-privacy.html.
"""
VERSION = "2026-11-25"

SECTIONS = [
    {"id": "location", "title": "Konum ve kişi bilgileri", "items": [
        "Girdiğiniz kişi adları (etiketler), konumlar (harita bağlantısı, koordinat veya cihaz konumu), tercihler ve sonuçlar yalnızca oturum süresince sunucu belleğinde tutulur. En geç iki saat sonra silinir; sunucu yeniden başlarsa daha erken kaybolabilir.",
        "Ham harita bağlantıları ve rota ölçümleri kalıcı veritabanına yazılmaz. 'Senaryoyu sil' veya 'Buluşma verilerimi sil' ile verilerinizi istediğiniz an silebilirsiniz.",
        "Yalnızca paylaşma yetkiniz olan kişilerin konumunu girin. Sağlık, kimlik, ödeme veya iletişim bilgisi girmeyin. Cihaz konumunuz yalnızca ilgili düğmeye bastığınızda alınır; arka planda konum takibi yapılmaz.",
        "Bu bildirimi onayladıktan sonra her konum girişinde ayrıca onay istenmez. Başkasının konumunu girmeden önce o kişinin izni olduğundan emin olun.",
    ]},
    {"id": "google", "title": "Google Maps hizmetleri", "items": [
        "Mekân ararken ve yol sürelerini hesaplarken konumlar ile seçtiğiniz mekân türleri Google Geocoding, Places ve Routes hizmetlerine gönderilir. Kısa harita bağlantıları çözülürken Google'a ağ isteği yapılabilir.",
        "Başlangıç noktasını yer adıyla aradığınızda (ör. 'Ankara Kalesi') yazdığınız metin Google Geocoding hizmetine gönderilir; ORTAK bu metni kaydetmez.",
        "Mekân adı, adres, puan, değerlendirme sayısı, fiyat seviyesi ve yol süreleri Google'dan gelir ve tahmindir. Fiyat seviyesi TL tutarı değildir; açık olma, rezervasyon, bilet veya uygunluk garantisi yoktur.",
        "Yol tarifi bağlantıları yalnızca hedef mekânı içerir; kişi konumlarınızı içermez. Google'ın kendi gizlilik politikası ayrıca geçerlidir.",
    ]},
    {"id": "transport", "title": "Ulaşım biçimi ve yol süreleri", "items": [
        "Her kişi için araç, toplu taşıma, yürüme veya bisiklet seçebilirsiniz; seçmezseniz grubun varsayılan biçimi kullanılır. Süreler bu seçime göre Google tarafından ayrı ayrı hesaplanır.",
        "Toplu taşıma, yürüme ve bisiklet süreleri saat, hat ve bölgeye göre değişebilir; her şehirde veya her konum için rota dönmeyebilir. Rota bulunamazsa hangi kişi için olduğu söylenir ve o kişinin ulaşım biçimini değiştirmeniz istenir. Seçtiğiniz ulaşım biçimi o kişinin konumuyla birlikte Google'a iletilir. Kişiler farklı yollarla geliyorsa yol tarifi bağlantısında ulaşım biçimi belirtilmez.",
    ]},
    {"id": "venues", "title": "Mekân ve etkinlik türleri", "items": [
        "Bir aramada en fazla beş tür seçebilirsiniz; sonuçlar seçtiğiniz türler arasında dengeli dağıtılır. Kaçış odası, bilardo, kutu oyunu kafesi, tırmanış ve trambolin için Google'da ayrı bir kategori yoktur; bu türlerde yalnızca adı etkinliğe uyan mekânlar gösterilir. Hiçbir türde etkinliğin o gün yapılabildiği, açık olduğu veya yer bulunduğu garanti edilmez.",
        "Alkol servisi yapan bar, pub veya gece kulübü türleri yalnızca siz seçerseniz aranır. Yaş sınırı, güvenlik ve sağlık koşullarını mekânla ayrıca doğrulayın.",
    ]},
    {"id": "ai", "title": "Yapay zekâ (Meta Llama 3)", "items": [
        "Tercihinizi doğal dille yazarsanız metin, uygulama sunucusunda çalışan Meta Llama 3 modeline gönderilir. Tanınan kişi adları gönderim öncesinde anonim etiketlere çevrilir; konum alanları modele eklenmez. Otomatik bulut modeline geçiş yoktur.",
        "Tercih alanına konum veya kişisel bilgi yazmayın. Ham metin ve model cevabı kalıcı kaydedilmez. Model önerileri sizin onayınızla uygulanır ve hata yapabilir.",
        "Yapay zekâ önerisini bildirirseniz yalnızca sorun türü ve kriter ağırlıkları 30 gün saklanır; metniniz veya konumlarınız eklenmez.",
    ]},
    {"id": "group", "title": "Odalar, davetler ve oylama", "items": [
        "Oda bağlantısını istediğiniz uygulamada paylaşabilirsiniz. Bağlantıyı açan herkes adını yazıp odaya katılabilir ve kendi başlangıç noktasını ekler; bu yüzden bağlantıyı yalnızca buluşacağınız kişilerle paylaşın. Oda sahibi istemediği kişiyi odadan çıkarabilir.",
        "Oda sahibi katılanların adlarını, konum ekleyip eklemediklerini ve ulaşım biçimlerini görür; başlangıç noktaları aramada kullanılır. Üyeler birbirlerinin konumunu görmez, yalnızca önerilen mekânları ve toplam oyları görür.",
        "Odayı kaydederseniz oda adı ile üyelerin adları ve ulaşım tercihleri sunucuda saklanır. Konumlar, oylar ve sonuçlar saklanmaz; her buluşmada en geç iki saatte silinir. 90 gün kullanılmayan kayıtlı odalar silinir; 'Kaydı sil' ile hemen silebilirsiniz. Bağlantılar ve anahtarlar sunucuda yalnızca özet (hash) olarak tutulur.",
        "Eski sürümlerdeki kişiye özel davet bağlantıları başkasına iletilmemelidir. Paylaşımı geri çekmek konumu ve oyu siler; düzenleyene daha önce aktarılmış kopyayı geri almaz.",
    ]},
    {"id": "plan", "title": "Buluşma planı", "items": [
        "Buluşma Planı isteğe bağlıdır. Şehir veya semt gibi yaklaşık bilgiler, kişi sayısı ve etkinlik tercihleri kullanılır; tam adres girmeyin. Plan fikirleri sınırlı bir etkinlik kataloğundan gelir, Google araması yapmaz. 'ORTAK'ta mekân bul' aktarımı isteğe bağlıdır ve kendiliğinden arama başlatmaz.",
    ]},
    {"id": "storage", "title": "Çerezler ve cihazda saklanan bilgiler", "items": [
        "Web sürümü imzalı, HttpOnly ve Secure bir oturum çerezi kullanır; iki saat geçerlidir ve senaryonuzu diğer ziyaretçilerden ayırmak için zorunludur. Reklam veya analitik çerezi ve SDK'sı yoktur.",
        "Tarayıcıda tema tercihiniz, bu bildirimi onayladığınıza dair kayıt (sürüm ve tarih), kaydettiğiniz odaların adı ve anahtarı ile katıldığınız odaların katılım anahtarı tutulur. Mobil uygulama onay kaydını ve kayıtlı odalarınızı cihazın güvenli deposunda (iOS Keychain, Android Keystore) saklar, yedeğe girmez; konum ve sonuçları dosyaya yazmaz.",
    ]},
    {"id": "hosting", "title": "Barındırma ve işletim kayıtları", "items": [
        "Arayüz Vercel üzerinden sunulur ve istekler Oracle'daki uygulama sunucusuna iletilir; yönlendirme bileşeni konumları, tercih metnini ve oturum çerezlerini kaydetmez. Vercel ve Oracle'ın kendi kayıt politikaları ayrıca geçerlidir. Google servisleri ve altyapı sağlayıcıları verileri yurt dışında işleyebilir.",
        "Kota ve harcama kontrolü için yalnızca Google işlem türü, zaman, durum, süre ve maliyet rezervasyonu saklanır; konum, mekân içeriği veya tercih cümlesi içermez. Hız sınırları anonim oturum kimliği ve günlük değişen IP özetiyle tutulur; ham IP veritabanına yazılmaz.",
    ]},
    {"id": "region", "title": "Bölge ve kullanım koşulları", "items": [
        "ORTAK Türkiye için hazırlanmıştır: Google aramaları Türkçe ve Türkiye bölgesiyle yapılır. Diğer ülkelerde mekân, fiyat ve toplu taşıma verileri eksik veya farklı olabilir.",
        "ORTAK üyeliksizdir ve yalnızca öneri üretir; sonuçlar tavsiyedir. Ayrıntılar için Gizlilik ve Kullanım koşulları sayfalarına bakabilirsiniz.",
    ]},
]
