# SciSciScout — Bilimsel ve Mühendislik Araştırma Asistanı 🧪

> **Sciscout**: bilimsel kaşif — kulkanıcı sorusu → 3-ajanlı deep research → yanıt + kaynaklar.

SciScout, güvenilir bilimsel/mühendislik kaynaklarını (arXiv, Semantic Scholar,
PubMed, Wikipedia, GitHub, StackExchange, Reddit) ve genel_web aramayı (Tavily,
trusted domains filtreli) birleştiren bir AI araştırma asistanıdır.

## 🚀 Çalışır!

```bash
$ sciscout ask "Son 1 yılda karanlık madde alanında ne çıktı?"
```

→ Türkçe soru İngilizce'ye çevrilir → 9 kaynak aynı anda aranır →
→ en alâkalı 6 makale seçilir → her biri özetlenir → sentezlenir.

---

## ✨ Özellikler

- **3-ajan döngüsü** — `researcher → reader → synthesizer`
- **9 kaynak** en az 6'sı paralel:
  - arXiv, Semantic Scholar, PubMed (akademik makale)
  - Wikipedia (arka plan)
  - GitHub, StackExchange (mühendislik/kod)
  - Google Scholar (scrape), Reddit (forum)
  - Tavily Web Search (yalnızca `TRUSTED_DOMAINS` filtreli)
- **Çoklu LLM**: Google **Gemini** + **Groq** Llama 3.3 70B + **OpenRouter** yedek
- **PDF okuma** — arXiv'de tam metin PyMuPDF ile metne çevrilir
- **CLI + REST API** (FastAPI)
- **Otomatik Türkçe→İngilizce** sorgu çevirisi (akademik kaynaklar İngilizce)

## 📦 Kurulum

```bash
cd ~/aiporjelrbirinci/sciscout
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 🔑 API Anahtarları

`.env` dosyasını `.env.example`'tan kopyalayın ve anahtarları girin:

```bash
cp .env.example .env
# .env içine GEMINI_API_KEY=... ve GROQ_API_KEY=... ekleyin
```

| Anahtar | Nereden alınır | Ücretsiz? |
|--|--|--|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | ✅ Cömert |
| `GROQ_API_KEY` | https://console.groq.com/keys | ✅ Llama 3.3 70B |
| `OPENROUTER_API_KEY` | https://openrouter.ai/keys | 🔶 Bazı modeller ücretsiz |
| `CEREBRAS_API_KEY` | https://cloud.cerebras.ai | 🔶 |
| `TAVILY_API_KEY` | https://app.tavily.com | 🔶 1000/ay ücretsiz |
| `SEMANTIC_SCHOLAR_API_KEY` | https://www.semanticscholar.org/product/api | ✅ Anahtarsız çalışır |

> **Not**: Sadece en az 1 LLM anahtar gerekir (Gemini veya Groq).
> Diğerleri opsiyonel yedektir.

## 🎮 Kullanım

### CLI

```bash
# Durum kontrolü
sciscout status

# Tam araştırma döngüsü (en yaygın)
sciscout ask "Kuantum bilgisayar ile Shor algoritmasında 2024-25 gelişmeleri neler?"

# Sadece tek kaynaktan arama (LLM'siz, hızlı)
sciscout search "quantum entanglement" --source arxiv -n 5

# Etkileşimli mod (sohbet)
sciscout interactive

# FastAPI sunucu (Web UI için)
sciscout serve --port 8000
```

### REST API

Sunucu çalışınca:

```bash
# Sağlık
curl http://127.0.0.1:8000/health

# Soru sor
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Son 1 yılda karanlık madde领域inde ne çıktı?"}'

# Tek kaynak arama
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"transformer architecture","source":"arxiv","max_results":3}'
```

### Python API

```python
import asyncio
from sciscout.agents.graph import ResearchGraph

async def main():
    g = ResearchGraph()
    state = await g.run("GRB 221009A'nın yeni yorumları neler?")
    print(state["answer"])
    for c in state["citations"]:
        print(f"[^{c['n']}] {c['title']} — {c['url']}")

asyncio.run(main())
```

## 🧠 Mimari

```
USER SORUSU
    │
    ▼
┌──────────────────────────────────────────┐
│ 1. RESEARCHER AGENT                      │
│  - Türkçe→İngilizce çeviri (LLM)         │
│  - 9 kaynak paralel search               │
│  - LLM ile top-6 seçme                   │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ 2. READER AGENT                          │
│  - PDF indir + PyMuPDF (eğer abstract    │
│    kısa ve arXiv kaynağı ise)             │
│  - HTML scrape (eğer web kaynağı ise)     │
│  - LLM ile her kaynak için özet üret     │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ 3. SYNTHESIZER AGENT                     │
│  - Tüm özetleri birleştir                 │
│  - Bilimsel stillde cevap üret            │
│  - [^n] kaynak referansları ekler        │
└──────────────────────────────────────────┘
    │
    ▼
  NİHAI CEVAP + KAYNAK LİSTESİ
```

## 🛡️ Güvenlik

- **TRUSTED_DOMAINS** filtresi: sadece güvenilir bilimsel/mühendislik alan adları
- Tavily sonuçları çift filtrelenir (Tavily + güvenilir alan kontrolü)
- LLM'ler `temperature=0.2-0.4` ile kontrol altında — halüsinasyon riski düşürülür
- Yanlış kaynak atıfları LLM'e `[^n]` formatı ile öğretilir
- Sistem boş cevap dönerse kullanıcıya güvenle bildirir

## 📁 Proje Yapısı

```
sciscout/
├── .env                # API anahtarları (git'e gönderilmez)
├── .env.example
├── pyproject.toml
├── README.md
├── sciscout/
│   ├── config.py       # Pydantic config
│   ├── cli.py          # Typer CLI
│   ├── sources/        # 9 kaynak modülü
│   │   ├── arxiv.py
│   │   ├── semantic_scholar.py
│   │   ├── pubmed.py
│   │   ├── wikipedia.py
│   │   ├── github.py
│   │   ├── stackoverflow.py
│   │   ├── scholar.py
│   │   ├── forums.py
│   │   └── web.py
│   ├── llm/            # LLM istemcileri
│   │   ├── gemini.py
│   │   ├── groq_client.py
│   │   └── router.py   #Birincil/yedek seçimi
│   ├── agents/         # 3-ajan döngüsü
│   │   ├── researcher.py
│   │   ├── reader.py
│   │   ├── synthesizer.py
│   │   └── graph.py
│   └── api/
│       └── server.py   # FastAPI
└── tests/
```

## 🧭 Soru örnekleri

- "Son 2 yılda LLM'lerde收取context pencere sınırlarına dair yeni makaleler?"
- "Mühendislikte CFD'le çözülen doğal konveksiyon problemlerinde makine öğrenmesi yaklaşımı"
- "LZ karanlık madde deneyinin 2024 sonuçları"
- "Tersinir mantık kapıları ile yeni kuvantum devre sentezi"
- "Batuhan/ChatGPT en sevdiğim metin — hakemli makale örneği"

## 🧪 Test

```bash
sciscout status
sciscout ask "Higgs bozonu son 5 yılda yeni ölçümler nedir?"
```

## 📝 Lisans

MIT — özgürce kullan, geliştir.

## 🤝 Katkı

İyileştirme önerileri için PR gönderin. Özellikle:
- Yeni kaynak entegrasyonları (DOAJ, IEEE Xplore, ResearchGate)
- PDF parsing iyileştirme
- Web UI detayları
- Citation network — Semantic Scholar grafik API
