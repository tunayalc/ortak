# ORTAK

ORTAK (Optimum Rota Tabanlı Adil Kesişim), grup buluşmaları için açıklanabilir mekân önerileri üreten bir web prototipidir. Ürün ekranında puan, fiyat ve kişi yakınlığı ayrı ağırlıklandırılır; rapordaki adalet-verim modeli araştırma karşılaştırmaları için korunur.

## Özellikler

- FastAPI backend, React + Vite frontend, SQLite cache/veri deposu
- Google Places API (New), Geocoding API ve Routes API desteği
- API anahtarı yokken deterministik sentetik aday ve rota üretimi
- Ürün ekranında kriter bazlı puan, fiyat uygunluğu ve kişi yakınlığı ağırlıkları
- Kişi başına yakınlık ağırlığı ve tek tuşla eşit kişi ağırlıkları
- Araştırma katmanında `lambda` dengesi: `0=min-sum/verim`, `1=min-max/adalet`
- Kişi sayısı kadar Google Maps linki veya `lat,lng` koordinatıyla session-only konum girişi
- Ollama üzerinden yerel doğal dil tercih yorumlama ve kullanıcı onaylı ağırlık önerisi
- İnno Derneği uygulamasından uyarlanan açık/koyu tema
- Top-K öneriler, skor kırılımı, kişi bazlı süreler ve Google Maps yol tarifi linkleri
- Rastgele tekrar ortalaması, coğrafi merkez, minimum-toplam süre ve minimum-maksimum süre temel yöntem karşılaştırmaları

## Hızlı Başlangıç

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.lock
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5174
```

Uygulama: http://127.0.0.1:5174
API: http://127.0.0.1:8000/docs

## Google Maps Ayarı

`.env` dosyasına aşağıdaki değişkeni ekleyin:

```bash
GOOGLE_MAPS_API_KEY=your_api_key_here
GOOGLE_MAPS_CALLS_ENABLED=false
GOOGLE_MAPS_DAILY_CALL_LIMIT=33
```

Anahtar yoksa uygulama sentetik adaylar ve OSRM/sentetik rotalarla çalışır. Bu mod, arayüz ve skorlama akışını test etmek içindir; gerçek Google rota iddiası için canlı test yapılmalıdır. Yeni Cloud projelerinde Places API (New), Routes API ve Geocoding API etkinleştirilir. Google sürüş rotalarında `routingPreference=TRAFFIC_AWARE` kullanılır. Anahtarın tanımlı olması bağlantının doğrulandığı anlamına gelmez.

Google verili senaryolar yalnızca backend belleğinde tutulur. Google mekân ve rota içeriği kalıcı SQLite cache'ine yazılmaz. Google Places saklama istisnaları ve atıf kuralları dikkate alınır; sentetik/OSRM cache davranışı ayrı kalır. Google boş sonuç döndürürse sahte mekân veya rota Google kaynağıyla gösterilmez.

Google kurulum ve kontrollü yayın adımları: [Yayın kılavuzu](docs/yayin_kilavuzu.md). Özel faturalandırma kanıtları açık kaynak depoda paylaşılmaz. Kurgusal üç katılımcı ve üç adayla kontrollü HTTP duman testi:

```bash
cd backend
.venv/bin/python scripts/evaluate_google_maps.py --live --max-spend-tl <onaylanan-TL>
```

Her çalışma `output/google_maps/<UTC-tarih>/` altında `run.json`, `stages.csv`, `report.md` ve anahtar içermeyen `source.tar.gz` üretir. API anahtarı veya harcama onayı eksikse `blocked` kaydı üretilir; gerçek Google testi başarılı sayılmaz. Fatura tutarı Google Cloud Billing belgesinden doğrulanır, çağrı sayısından ücret uydurulmaz.

Google çağrıları varsayılan olarak kapalıdır. Faturalandırma ve bütçe onayından sonra `GOOGLE_MAPS_CALLS_ENABLED=true` açılır. İlk testte toplam günlük deneme sınırı 33'tür; yeniden denemeler dâhil SQLite sayacı servis yeniden başlatıldığında korunur. Sayaç yalnızca bu backend/veritabanını kapsar, TL tutarını veya başka uygulamaların kullanımını sınırlamaz. Test bitince çağrılar yeniden kapatılır.

## OSRM Yedeği

Google anahtarı yoksa `auto` sağlayıcısında sürüş modu için OSRM denenir. OSRM de yanıt vermezse sistem deterministik sentetik sürelere iner. Gerçek Google testinde `provider=google` zorunludur; hata veya kota sınırı sentetik başarıya çevrilmez.

```bash
OSRM_BASE_URL=http://router.project-osrm.org
```

## Ürün Skoru ve Lambda Dengesi

Ürün ekranındaki varsayılan skor şöyledir:

```text
final_score = w_rating * rating_norm + w_cost * cost_norm + w_proximity * proximity_norm
proximity_norm = sum(person_weight_i * closeness_norm_i)
```

Varsayılan kriter ağırlıkları puan `%34`, fiyat `%33`, yakınlık `%33` değerleridir. Kişiler başlangıçta eşit ağırlıktadır. Fiyat verisi bilinmiyorsa o adayın fiyat uygunluğu nötr `0.5` kabul edilir.

Rapor uyumlu karşılaştırma modunda `lambda=0` minimum-toplam süreye, `lambda=1` minimum-maksimum süreye karşılık gelir:

```text
fairness_norm = 1 - norm(t_max)
efficiency_norm = 1 - norm(t_sum)
S_lambda = lambda * fairness_norm + (1 - lambda) * efficiency_norm
```

Bu modda kalite skoru eşit skorları kırmak ve öneriyi açıklamak için kullanılır. Ürün ekranındaki kriter bazlı modda mekân puanı doğrudan ana skorun parçasıdır.

## Kişi Konumu ve Gelişmiş Öncelikler

Arayüzde `Sentetik konum` ve `Link ile kişi konumu` modları bulunur. Link modunda her katılımcı için Google Maps linki veya `lat,lng` koordinatı girilir; ham linkler SQLite'a yazılmaz ve bu senaryolar yalnızca backend belleğinde oturumluk tutulur. Backend yeniden başlatılırsa bu senaryolar silinir.

Geriye uyumlu gelişmiş öncelik API modu, rapor skoru, mekân puanı, fiyat uygunluğu ve odak yakınlığını şu biçimde birleştirir:

```text
advanced_score =
  w_report * S_lambda +
  w_quality * quality_norm +
  w_cost * cost_norm +
  w_focus * focus_norm
```

Ürün ekranındaki kişi deltası, ilgili kişinin yakınlık kriterindeki payını belirler. Süre deltası yalnızca geriye uyumlu gelişmiş API yolunda ayrı bir seçenektir. Özel koordinatlı kullanıcı listeleri eski API yolunda varsayılan olarak kabul edilmez; yalnızca açıkça `synthetic_fixture=true` gönderilen kurgusal test senaryolarında kullanılabilir.

## Doğal Dil Tercih Yorumu

Varsayılan sağlayıcı **Ollama**, yerel model **llama3:8b** değeridir; OpenAI anahtarı gerekmez. Ollama uygulamasını açın veya ayrı bir terminalde `ollama serve` çalıştırın. `ollama list` ile modelin bulunduğunu doğrulayın. Model kurulu değilse `ollama pull llama3:8b` komutuyla indirilebilir; ORTAK otomatik indirme yapmaz. Önceki Qwen modeli, `OLLAMA_MODEL=qwen2.5:3b` ayarlanarak kullanılabilir.

Backend `.env` ayarları:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3:8b
```

`POST /preferences/interpret` Türkçe tercih cümlesini puan, fiyat, yakınlık, kişi ağırlıkları ve açıkça söylenen sayısal filtreler için **düzenlenebilir bir öneriye** dönüştürür. Yerel model, JSON Schema ile yalnızca istenen değişiklikleri ve istek içindeki dayanak ifadelerini çıkarır. Backend bunları doğrular, belirtilmeyen ayarları korur ve açıklamayı doğrulanmış değerlerden üretir. Kişi ağırlığı ile genel yakınlık kriteri ayrı işlenir. Ağırlıklar öneri ekranında normalize edilmiş yüzdelerle gösterilir; kullanıcı “Değerleri uygula” düğmesine basmadan sıralama değişmez.

`GET /health` yanıtındaki `ai_provider`, `ai_model`, `ai_configured`, `ai_ready` ve `ai_status` alanları bağlantı durumunu gösterir. Ollama için `ready`, `model_missing`, `unreachable` ve `timeout` durumları ayrıdır. Model bulunması üretim doğruluğu garantisi değildir. Arayüzde bağlantı yenileme düğmesi bulunur. Bağlantı zaman aşımı 3, çıkarım bekleme süresi 120 saniyedir. Hatalı veya eksik yanıtlar ayarları değiştirmez; manuel seçim her durumda kullanılabilir.

OpenAI ancak `LLM_PROVIDER=openai` ve `OPENAI_API_KEY` açıkça ayarlanırsa kullanılır; `OPENAI_MODEL` varsayılanı `gpt-4o-mini` değeridir. OpenAI durumundaki `configured`, yalnızca anahtar tanımlı demektir, canlı bağlantı doğrulaması değildir. Otomatik bulut yedeği yoktur. `LLM_PROVIDER=disabled` LLM özelliğini kapatır.

Kişi konum alanları model isteğine dahil edilmez. Tercih metninde tanınan konum bağlantıları ve koordinatlar reddedilir; bu alana kişisel konum bilgisi yazılmamalıdır. Kişi etiketleri model çağrısı öncesinde `Kişi 1`, `Kişi 2` biçiminde değiştirilir. Ham istek, yanıt veya sohbet geçmişi uygulama tarafından SQLite'a ya da dosyaya kaydedilmez. Açıkça seçilen OpenAI yolunda `store=false` kullanılır; sağlayıcının kendi veri politikası ayrıca geçerlidir.

**Yerel çalışma yalnızca Ollama LLM adımı içindir.** Google Maps ve OSRM, kullanıldığında harici servislerdir. Gerçek kişi konumlarının oturumluk saklama kuralı değişmez. Bu özellik önceden eğitilmiş model entegrasyonudur; ORTAK için yeni model eğitildiği iddia edilmez.

Canlı değerlendirme yalnızca sabit, kurgusal test cümleleri kullanır ve bu testlerin sonuçlarını dosyaya yazar:

```bash
cd backend
.venv/bin/python scripts/evaluate_preferences.py --output ../output/ollama/evaluation.json --repeats 3
```

Sonuçlar ve sınırlamalar: `docs/ollama_dogrulama.md`. Bu küçük geliştirme setindeki başarı, genel Türkçe doğruluğu veya güvenlik garantisi değildir.

Rapor uyum taslağı: `docs/rapor_uyum_taslagi.md`
Yayın ve geri dönüş: [Yayın kılavuzu](docs/yayin_kilavuzu.md)

## Testler

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm run build
npm run test:e2e
```
