"""SciScout CLI — Typer + Rich ile şık terminal arayüzü.

Komutlar:
    sciscout ask "karanlık madde son keşifler"
    sciscout search "quantum entanglement" --source arxiv
    sciscout interactive
    sciscout serve
    sciscout status
    sciscout config         # interaktif ayar düzenleyici
    sciscout config --list  # mevcut ayarları göster
    sciscout config --set SCI_MODEL_PRIMARY=groq:llama-3.3-70b-versatile
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .agents.graph import ResearchGraph
from .config import check_configuration, get_settings

app = typer.Typer(
    name="sciscout",
    help="SciScout — bilimsel/mühendislik araştırma agentı",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, show_time=True)],
    )


def _provider_label(name: str) -> str:
    colors = {
        "gemini": "bright_yellow",
        "groq": "bright_green",
        "cerebras": "bright_magenta",
        "openrouter": "bright_blue",
    }
    color = colors.get(name.lower(), "white")
    return f"[{color}]{name}[/{color}]"


# ---------------- status ----------------


@app.command()
def status():
    """Yapılandırma ve API sağlayıcı durumunu göster."""
    s = get_settings()
    ok, issues = check_configuration()

    table = Table(
        title="[bold cyan]SciScout Sağlayıcı Durumu[/bold cyan]",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
    )
    table.add_column("Sağlayıcı", style="bold")
    table.add_column("Anahtar var mı?", justify="center")
    table.add_column("Model", style="dim")

    rows = [
        ("Gemini", bool(s.gemini_api_key), "gemini-2.5-flash"),
        ("Groq", bool(s.groq_api_key), "llama-3.3-70b-versatile"),
        ("Cerebras", bool(s.cerebras_api_key), "gemma-4-31b"),
        ("OpenRouter", bool(s.openrouter_api_key), s.model_fallback),
        ("Tavily", bool(s.tavily_api_key), "web search"),
        ("S2 Scholar", bool(s.semantic_scholar_api_key), "(opsiyonel)"),
        ("NASA ADS", bool(s.nasa_ads_api_key), "astrofizik DB"),
    ]
    for name, has, model in rows:
        table.add_row(
            _provider_label(name),
            "[green]✓ evet[/green]" if has else "[red]✗ hayır[/red]",
            model,
        )
    console.print(table)

    try:
        from .llm.router import LLMRouter

        r = LLMRouter()
        if r.has_any():
            chain_str = " → ".join(f"{c.provider}/{c.model}" for c in r._ordered)
            console.print(f"\n[bold]Yedekleme zinciri:[/bold] {chain_str}")
    except Exception as e:
        console.print(f"[yellow]Router örnekleme hatası: {e}[/yellow]")

    if issues:
        for i in issues:
            console.print(f"[yellow]⚠ {i}[/yellow]")
    if ok:
        console.print("\n[green]✓ Yapılandırma hazır. Başlayabilirsin![/green]")
    console.print(f"\n[dim].env konumu: {ENV_PATH}[/dim]")


# ---------------- config ----------------


def _read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _write_env(data: dict[str, str]) -> None:
    lines = []
    seen = set()
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                k = stripped.split("=", 1)[0].strip()
                if k in data:
                    lines.append(f"{k}={data[k]}")
                    seen.add(k)
                    continue
            lines.append(line)
    for k, v in data.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.command()
def config(
    list_keys: bool = typer.Option(False, "--list", "-l", help="Ayarları listele"),
    set_kv: Optional[str] = typer.Option(None, "--set", "-s", help="KEY=VALUE ayarla"),
):
    """İnteraktif ayar düzenleyici veya CLI üzerinden ayarlar."""
    if list_keys:
        _show_config()
        return
    if set_kv:
        if "=" not in set_kv:
            console.print(
                "[red]Geçersiz format. Örnek: --set SCI_MODEL_PRIMARY=groq:llama-3.3-70b-versatile[/red]"
            )
            raise typer.Exit(1)
        k, v = set_kv.split("=", 1)
        data = _read_env()
        data[k.strip()] = v.strip()
        _write_env(data)
        console.print(f"[green]✓ {k} = {v}[/green]")
        return

    console.print(
        Panel(
            "[bold]SciScout Ayarlar Menüsü[/bold]\n\nBu menü .env dosyanızı düzenler.",
            border_style="cyan",
        )
    )

    keys = [
        ("GEMINI_API_KEY", "Google Gemini API anahtarı", "Al: https://aistudio.google.com/apikey"),
        (
            "GROQ_API_KEY",
            "Groq API anahtarı (LLama 3.3 70B — ana önerilen)",
            "Al: https://console.groq.com/keys",
        ),
        (
            "CEREBRAS_API_KEY",
            "Cerebras API anahtarı (Gemma 4 31B)",
            "Al: https://cloud.cerebras.ai",
        ),
        (
            "OPENROUTER_API_KEY",
            "OpenRouter (100+ model)",
            "Al: https://openrouter.ai/keys (opsiyonel)",
        ),
        ("TAVILY_API_KEY", "Tavily web search", "Al: https://app.tavily.com (opsiyonel)"),
        (
            "NASA_ADS_API_KEY",
            "NASA ADS astrofizik DB",
            "Al: https://ui.adsabs.harvard.edu/user/settings/token (opsiyonel)",
        ),
        ("SCI_MODEL_PRIMARY", "Ana model)", "Önerilen: groq:llama-3.3-70b-versatile"),
        ("SCI_MODEL_FAST", "Hızlı model (çeviri/kısa)", "Önerilen: cerebras:gemma-4-31b"),
        ("SCI_MODEL_FALLBACK", "Yedek model", "Önerilen: gemini:gemini-2.5-flash"),
        ("SCI_MAX_PAPERS_PER_QUERY", "Sorgu başına makale sayısı", "Önerilen: 12"),
        ("SCI_MAX_WEB_RESULTS", "Web arama sonucu sayısı", "Önerilen: 10"),
        ("SCI_PDF_READ", "PDF tam metin okuma (True/False)", "Önerilen: True"),
    ]

    data = _read_env()
    for key, desc, hint in keys:
        cur = data.get(key, "")
        masked = ""
        if "API_KEY" in key and cur:
            masked = f"  [dim](mevcut: {cur[:6]}***{cur[-4:] if len(cur) > 10 else '***'})[/dim]"
        console.print(f"\n[bold cyan]{key}[/bold cyan] — {desc}")
        console.print(f"  [dim]{hint}[/dim]{masked}")
        new_val = Prompt.ask("  Yeni değer (boş = koru)", default=cur, show_default=False)
        if new_val and new_val != cur:
            data[key] = new_val

    if Confirm.ask("\nAyarları kaydet?", default=True):
        _write_env(data)
        console.print("[green]✓ .env kaydedildi.[/green]")
    else:
        console.print("[yellow]İptal edildi.[/yellow]")


def _show_config():
    data = _read_env()
    table = Table(
        title="[bold cyan]Mevcut Ayarlar[/bold cyan]", show_header=True, header_style="bold cyan"
    )
    table.add_column("Anahtar")
    table.add_column("Değer")
    for k, v in data.items():
        if "API_KEY" in k and v:
            v_display = f"{v[:6]}***{v[-4:] if len(v) > 10 else '***'}"
        else:
            v_display = v or "(boş)"
        table.add_row(k, v_display)
    console.print(table)


# ---------------- ask ----------------


@app.command()
def ask(
    question: str = typer.Argument(..., help="Soru"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Bir soru sor, tam araştırma döngüsü yap."""
    _setup_logging(verbose)
    ok, issues = check_configuration()
    if not ok:
        for i in issues:
            console.print(f"[red]✗ {i}[/red]")
        raise typer.Exit(code=1)

    console.print(
        Panel(f"[bold]{question}[/bold]", title="[bold cyan]Soru[/bold cyan]", border_style="cyan")
    )
    console.print("[dim]Araştırılıyor... (30-90 sn sürebilir)[/dim]\n")

    graph = ResearchGraph()
    state = asyncio.run(graph.run(question))

    answer = state.get("answer", "(cevap yok)")
    console.print()
    console.print(
        Panel(Markdown(answer), title="[bold green]Cevap[/bold green]", border_style="green")
    )

    citations = state.get("citations", [])
    if citations:
        console.print("\n[bold cyan]📄 Kaynaklar[/bold cyan]")
        for c in citations:
            console.print(
                f"[bold][^{c['n']}][/bold] [bold]{c.get('title', '?')[:90]}[/bold]"
                f"  [dim]({c.get('source', '?')})[/dim]"
            )
            console.print(f"   [link={c.get('url', '')}]{c.get('url', '')}[/link]")

    per_source = state.get("per_source_counts", {})
    if per_source:
        t = Table(
            title="[bold cyan]Kaynak bazında bulunan doküman sayısı[/bold cyan]",
            show_header=True,
            header_style="bold cyan",
        )
        t.add_column("Kaynak")
        t.add_column("Sayı", justify="right")
        for k, v in per_source.items():
            t.add_row(k, str(v) if v else "[red]0[/red]")
        console.print(t)


# ---------------- search ----------------


@app.command()
def search(
    query: str = typer.Argument(...),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="arxiv|semantic_scholar|pubmed|europe_pmc|wikipedia|github|stackoverflow|scholar|forums|web|nasa_ads|doaj",
    ),
    max_results: int = typer.Option(5, "--max", "-n"),
):
    """Tek kaynakta arama (LLM kullanmaz)."""
    from .sources import (
        ADSSource,
        ArxivSource,
        DOAJSource,
        EuropePMCSource,
        ForumsSource,
        GitHubSource,
        GoogleScholarSource,
        PubMedSource,
        SemanticScholarSource,
        StackOverflowSource,
        WebSource,
        WikipediaSource,
    )

    sources_map = {
        "arxiv": ArxivSource,
        "semantic_scholar": SemanticScholarSource,
        "pubmed": PubMedSource,
        "europe_pmc": EuropePMCSource,
        "wikipedia": WikipediaSource,
        "github": GitHubSource,
        "stackoverflow": StackOverflowSource,
        "scholar": GoogleScholarSource,
        "forums": ForumsSource,
        "web": WebSource,
        "nasa_ads": ADSSource,
        "doaj": DOAJSource,
    }
    if source and source not in sources_map:
        console.print(f"[red]Bilinmeyen kaynak: {source}[/red]")
        console.print(f"Geçerli: {', '.join(sources_map.keys())}")
        raise typer.Exit(1)

    names = [source] if source else list(sources_map.keys())

    async def _go():
        results = {}
        for n in names:
            try:
                if n == "nasa_ads":
                    s = sources_map[n](
                        max_results=max_results, api_key=get_settings().nasa_ads_api_key
                    )
                else:
                    s = sources_map[n](max_results=max_results)
                docs = await s.search(query)
                results[n] = docs
            except Exception as e:
                results[n] = []
                console.print(f"[yellow]⚠ {n}: {e}[/yellow]")
        return results

    results = asyncio.run(_go())

    for n, docs in results.items():
        if not docs:
            continue
        console.print(f"\n[bold cyan][{n}][/] ({len(docs)} sonuç)")
        for i, d in enumerate(docs, 1):
            console.print(f"  [bold]{i}. {d.title}[/bold]")
            console.print(f"     [link={d.url}]{d.url}[/link]")
            if d.authors:
                console.print(f"     [dim]Yazarlar: {', '.join(d.authors[:3])}[/dim]")
            if d.snippet:
                console.print(f"     [dim]{d.snippet[:150]}...[/dim]")


# ---------------- interactive ----------------


@app.command()
def interactive():
    """Etkileşimli sohbet modu."""
    _setup_logging(False)
    ok, _ = check_configuration()
    if not ok:
        console.print("[red].env dosyasını yapılandırın (sciscout config).[/red]")
        raise typer.Exit(1)

    graph = ResearchGraph()
    console.print(
        Panel(
            "[bold cyan]SciScout Interactive[/bold cyan]\nÇıkmak için 'exit' veya Ctrl+C",
            border_style="cyan",
        )
    )
    while True:
        try:
            q = Prompt.ask("\n[bold]Soru[/bold]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Çıkış...[/dim]")
            break
        if q.strip().lower() in {"exit", "quit", "çıkış", "çık", "cikis", "cik"}:
            break
        if not q.strip():
            continue
        console.print("[dim]Araştırılıyor...[/dim]")
        state = asyncio.run(graph.run(q))
        console.print(
            Panel(
                Markdown(state.get("answer", "")),
                title="[bold green]Cevap[/bold green]",
                border_style="green",
            )
        )


# ---------------- serve ----------------


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False),
):
    """FastAPI server'ı başlat."""
    import uvicorn

    uvicorn.run(
        "sciscout.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
