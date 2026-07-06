# SciScout — Scientific & Engineering Research Agent

> **Kısa Özet (TR):**  
> SciScout, bilimsel ve mühendislik sorularını güvenilir kaynaklardan araştıran çok ajanlı bir AI araştırma asistanıdır.  
> 12 farklı kaynaktan (arXiv, Semantic Scholar, PubMed, NASA ADS, vb.) veri toplar, makaleleri okur ve kaynaklı yanıt üretir.  
> Türkçe dahil çok dilli soruları İngilizce akademik sorguya çevirir.  
> CLI ve FastAPI REST API ile hem terminalde hem sunucu modunda çalışır.  
> Self-host edilebilir; yalnızca gerekli API anahtarları yeterlidir.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Enabled-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%E2%80%A2%20Cerebras%20%E2%80%A2%20Gemini%20%E2%80%A2%20OpenRouter-purple.svg)](#api-keys)
[![Sources](https://img.shields.io/badge/Sources-12%20trusted%20sources-success.svg)](#sources-we-search)

**Tagline:**  
**AI agent that answers scientific/engineering questions by searching 12 trusted sources, reading papers, and synthesizing answers.**

---

## Hero

**TR:** SciScout, bilimsel ve mühendislik sorularını güvenilir kaynaklardan tarayan, ilgili makale/içerikleri okuyup atıflı yanıtlar üreten bir araştırma ajanıdır.  
Türkçe veya başka bir dilde gelen soruları akademik arama için uygun İngilizce sorguya çevirir.  
CLI ve REST API ile hem geliştiriciler hem araştırmacılar için hızlı bir iş akışı sunar.

**EN:** SciScout is an AI research agent for scientific and engineering questions.  
It searches trusted academic/technical sources, reads papers (including PDFs when needed), and returns synthesized answers with citations.  
It supports multilingual input, streams responses, and can run via CLI or FastAPI server.

---

## How does it work?

```text
USER QUESTION
    │
    ▼
[RESEARCHER] ──► [READER] ──► [SYNTHESIZER] ──► ANSWER + CITATIONS
```

- **Researcher:** query translation, multi-source retrieval, ranking
- **Reader:** abstract/PDF/content extraction and per-source summarization
- **Synthesizer:** final answer generation with inline citations

---

## Features

- 3-agent pipeline (**researcher, reader, synthesizer**)
- 12 trusted academic & engineering sources
- Multi-LLM router with automatic fallback (**Groq → Cerebras → Gemini**)
- Automatic Turkish/any-language → English query translation
- PDF full text extraction (PyMuPDF) when abstract is insufficient
- Inline citations `[^n]` with footnote-style sourcing
- Streaming responses
- Interactive CLI + REST API server
- No external services required to self-host (just API keys)

---

## Sources we search

| Source | Coverage | Auth |
|---|---|---|
| arXiv | Physics / CS / preprints | none |
| Semantic Scholar | Peer-reviewed literature | optional key |
| PubMed | Biomedical research | none |
| Europe PMC | Open-access biomedical content | none |
| NASA ADS | Astrophysics / cosmology | API key |
| DOAJ | Open-access journals | none |
| Wikipedia | General background context | none |
| GitHub | Code / engineering references | token (optional) |
| StackExchange | Q&A (13 sites) | none |
| Google Scholar | Broad academic index | (scrape) |
| Reddit | Community discussions | none |
| Tavily web | Trusted-domain web search | API key |

---

## Quickstart

```bash
git clone https://github.com/<USER>/sciscout.git
cd sciscout
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # fill API keys
sciscout status
sciscout ask "Latest dark matter detection experiments?"
```

### CLI commands

| Command | Description |
|---|---|
| `sciscout ask "<question>"` | Full research pipeline |
| `sciscout search "<query>" -s arxiv` | Single source search (no LLM) |
| `sciscout interactive` | Interactive chat mode |
| `sciscout serve --port 8000` | Start FastAPI REST server |
| `sciscout status` | Configuration & providers check |
| `sciscout config` | Interactive settings editor |
| `sciscout config --list` | List current settings |
| `sciscout config --set KEY=VALUE` | Set one setting |

### REST API (curl)

```bash
# Health
curl http://127.0.0.1:8000/health

# Ask
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Latest dark matter detection experiments?"}'

# Stream ask (SSE)
curl -N -X POST http://127.0.0.1:8000/ask/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"Summarize recent advances in quantum error correction."}'

# Search
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"transformer architecture","source":"arxiv","max_results":3}'
```

---

## Configuration

| Key | Purpose | Example |
|---|---|---|
| `SCI_MODEL_PRIMARY` | Primary model | `llama-3.3-70b-versatile` |
| `SCI_MODEL_FAST` | Fast/cheap model | `gemini-1.5-flash` |
| `SCI_MODEL_FALLBACK` | Fallback model | `gemini-1.5-pro` |
| `max_papers_per_query` | Max selected papers per question | `6` |
| `max_web_results` | Max web results | `8` |
| `pdf_read` | Enable PDF full-text extraction | `true` |

---

## API Keys

| Provider | Where to get it | Free tier? |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey | Yes |
| Groq | https://console.groq.com/keys | Yes |
| Cerebras | https://cloud.cerebras.ai | Limited |
| OpenRouter | https://openrouter.ai/keys | Partial |
| Tavily | https://app.tavily.com | Limited |
| Semantic Scholar | https://www.semanticscholar.org/product/api | Optional / mostly yes |
| NASA ADS | https://ui.adsabs.harvard.edu/help/api/ | Required for ADS endpoints |

> Never commit `.env`. Commit only `.env.example`.

---

## Project structure

```text
sciscout/
├── .env.example
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── pyproject.toml
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       └── ci.yml
└── sciscout/
    ├── cli.py
    ├── config.py
    ├── agents/
    ├── sources/
    ├── llm/
    └── api/
```

---

## Demo

> Placeholder image (replace later with real screenshot)

![SciScout Demo](assets/demo.png)

---

## Examples of questions

- “What are the latest dark matter direct-detection experiment results?”
- “Recent progress in quantum error correction for fault-tolerant computing?”
- “Best engineering practices for retrieval-augmented generation evaluation?”
- “What changed in transformer efficiency papers in the last 18 months?”

---

## Limitations

- Some sources may rate-limit or temporarily throttle requests.
- Google Scholar scraping can be brittle and may break over time.
- Result quality depends on source availability and model/provider health.

---

## Roadmap

- Web UI (Next.js)
- Citation network graph
- Per-source caching (Redis)
- Multi-turn conversational memory
- Voice/STT input
- LangGraph / proper agent framework integration

---

## License

MIT

---

## Acknowledgements

Google Gemini, Groq, Cerebras, OpenRouter, arXiv, Semantic Scholar, PubMed, Europe PMC, NASA ADS, DOAJ, Wikipedia, StackExchange, Reddit, Tavily.
