"""FastAPI server — REST API.

Endpoints:
  POST   /ask         Tam araştırma döngüsü (sync yanıt)
  POST   /ask/stream  Akışlı yanıt (SSE)
  POST   /search      Sadece kaynak arama (LLM'siz)
  GET    /health      Sağlık kontrolü
  GET    /sources     Kaynak listesini döndürür
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agents.graph import ResearchGraph
from ..config import check_configuration, get_settings
from ..llm.base import LLMMessage
from ..llm.router import LLMRouter
from ..sources import (
    ArxivSource,
    ForumsSource,
    GitHubSource,
    GitHubSource as _GS,
    GoogleScholarSource,
    PubMedSource,
    SemanticScholarSource,
    StackOverflowSource,
    WebSource,
    WikipediaSource,
)

logger = logging.getLogger("sciscout.api")


# ---------------- Pydantic modelleri ----------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    pdf_read: Optional[bool] = None


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[dict]
    summaries: list[dict]
    per_source_counts: dict
    selected_count: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    source: Optional[str] = None
    max_results: int = Field(default=6, ge=1, le=20)


# ---------------- Factory ----------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="SciScout API",
        description="Bilimsel ve mühendislik araştırma agentı",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Singleton graph
    graph: Optional[ResearchGraph] = None
    router: Optional[LLMRouter] = None

    def _get_graph() -> ResearchGraph:
        nonlocal graph
        if graph is None:
            graph = ResearchGraph()
        return graph

    def _get_router() -> LLMRouter:
        nonlocal router
        if router is None:
            router = LLMRouter()
        return router

    @app.get("/health")
    async def health():
        ok, issues = check_configuration()
        s = get_settings()
        return {
            "status": "ok" if ok else "degraded",
            "issues": issues,
            "providers": {
                "gemini": bool(s.gemini_api_key),
                "groq": bool(s.groq_api_key),
                "openrouter": bool(s.openrouter_api_key),
                "cerebras": bool(s.cerebras_api_key),
                "tavily": bool(s.tavily_api_key),
            },
        }

    @app.get("/sources")
    async def list_sources():
        return {
            "sources": [
                {"name": "arxiv", "description": "Fizik/CS/Matu/Denck preprints"},
                {"name": "semantic_scholar", "description": "Peer-reviewed makale veritabanı"},
                {"name": "pubmed", "description": "Biyoloji/Tıp makaleleri"},
                {"name": "wikipedia", "description": "Ansiklopedik arka plan"},
                {"name": "github", "description": "Kod/repo: mühendislik uygulamaları"},
                {"name": "stackoverflow", "description": "Tüm Stack Exchange siteleri"},
                {"name": "scholar", "description": "Google Scholar (scrape)"},
                {"name": "forums", "description": "Reddit bilim/mühendislik"},
                {"name": "web", "description": "Tavily tarayıcı (trusted URLs)"},
            ]
        }

    @app.post("/ask", response_model=AskResponse)
    async def ask(req: AskRequest):
        g = _get_graph()
        try:
            state = await g.run(req.question)
        except Exception as e:
            logger.exception("Research failed")
            raise HTTPException(status_code=500, detail=str(e))

        return AskResponse(
            question=req.question,
            answer=state.get("answer", ""),
            citations=state.get("citations", []),
            summaries=state.get("summaries", []),
            per_source_counts=state.get("per_source_counts", {}),
            selected_count=len(state.get("selected_documents", [])),
        )

    @app.post("/ask/stream")
    async def ask_stream(req: AskRequest):
        """Sentez agent'ının cevabını SSE olarak stream eder."""
        g = _get_graph()

        async def event_gen():
            try:
                # Önce araştır+oku (sync kısımlar)
                from ..agents.researcher import researcher_agent
                from ..agents.reader import reader_agent

                state = {
                    "question": req.question,
                    "settings": g.settings,
                    "router": g.router,
                }
                state = await researcher_agent(state)
                yield f"data: {json.dumps({'type': 'sources', 'count': len(state.get('selected_documents', []))})}\n\n"
                state = await reader_agent(state)
                yield f"data: {json.dumps({'type': 'summaries', 'count': len(state.get('summaries', []))})}\n\n"

                # Şimdi sentez stream (manuel)
                from ..agents.synthesizer import SYSTEM_PROMPT

                summaries = state.get("summaries", [])
                summaries_block = "\n\n---\n\n".join(
                    f"### Source {i}: {s['title']}\n{s['summary']}"
                    for i, s in enumerate(summaries, 1)
                )
                user_msg = (
                    f"USER QUESTION:\n{req.question}\n\n"
                    f"SUMMARIES:\n{summaries_block}\n\n"
                    f"Write a rigorous synthesis with [^n] citations."
                )

                answer_chunks = []
                async for token in g.router.stream(
                    [
                        LLMMessage(role="system", content=SYSTEM_PROMPT),
                        LLMMessage(role="user", content=user_msg),
                    ],
                    temperature=0.4,
                    max_tokens=4000,
                ):
                    answer_chunks.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'citations': [{'n': i, 'title': s['title'], 'url': s['url'], 'source': s['source']} for i, s in enumerate(summaries, 1)]})}\n\n"
            except Exception as e:
                logger.exception("stream failed")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    @app.post("/search")
    async def search(req: SearchRequest):
        """Tek kaynak araması — LLM çağrısı yapmaz."""
        sources = {
            "arxiv": ArxivSource,
            "semantic_scholar": SemanticScholarSource,
            "pubmed": PubMedSource,
            "wikipedia": WikipediaSource,
            "github": GitHubSource,
            "stackoverflow": StackOverflowSource,
            "scholar": GoogleScholarSource,
            "forums": ForumsSource,
            "web": WebSource,
        }
        if req.source and req.source not in sources:
            raise HTTPException(400, f"Bilinmeyen kaynak: {req.source}")
        names = [req.source] if req.source else list(sources.keys())

        async def _gather():
            results = []
            for n in names:
                s = sources[n](max_results=req.max_results)
                try:
                    results.append(
                        {"source": n, "items": [d.to_dict() for d in await s.search(req.query)]}
                    )
                except Exception as e:
                    results.append({"source": n, "error": str(e)})
            return results

        return {"query": req.query, "results": await _gather()}

    return app


# Module-level singleton
app = create_app()


def main():
    """uvicorn ile çalıştırma için: python -m sciscout.api.server"""
    import uvicorn

    uvicorn.run("sciscout.api.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
