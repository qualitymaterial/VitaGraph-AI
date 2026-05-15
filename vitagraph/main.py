import typer
import os
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from .config import config_manager, Config
from .core.ingest_rxiv import fetch_rss_feed, download_pdf, extract_text_from_pdf
from .core.extract import extract_relationships
from .core.graph import get_neo4j_driver, insert_extraction_result
from .core.hypothesis import find_missing_links, evaluate_hypothesis, generate_markdown_report
from .agent import ResearchOracle

app = typer.Typer(
    name="vitagraph",
    help="VitaGraph AI: Autonomous Longevity Research CLI",
    add_completion=False,
)
console = Console()

@app.command()
def research(
    topic: str = typer.Argument(..., help="Biological topic or compound to research"),
    limit: int = typer.Option(3, help="Max number of papers to ingest")
):
    """
    Run an autonomous research loop on a specific topic.
    """
    oracle = ResearchOracle(console=console)
    oracle.run_topic_research(topic, limit=limit)

@app.command()
def ingest(
    url: str = typer.Option("http://connect.biorxiv.org/biorxiv_xml.php?subject=aging", help="RSS feed URL"),
    limit: int = typer.Option(5, help="Limit number of papers"),
    output_dir: Optional[str] = typer.Option(None, help="Directory to save PDFs")
):
    """
    Fetch preprints from bioRxiv/medRxiv and download PDFs.
    """
    config = config_manager.config
    save_dir = output_dir or config.output_dir
    
    console.print(f"[bold green]Ingesting preprints from:[/bold green] {url}")
    entries = fetch_rss_feed(url)
    
    if not entries:
        console.print("[bold red]No entries found.[/bold red]")
        raise typer.Exit(1)

    processed = 0
    for entry in entries[:limit]:
        title = entry["title"]
        doi = entry["doi"]
        link = entry["link"]
        
        console.print(f"\n[cyan]Processing:[/cyan] {title}")
        
        clean_link = link.split('?')[0]
        pdf_url = clean_link + ".full.pdf" if not clean_link.endswith(".pdf") else clean_link
        
        safe_doi = doi.replace("/", "_") if doi else clean_link.split("/")[-1]
        filename = f"{safe_doi}.pdf"
        save_path = os.path.join(save_dir, filename)
        
        if download_pdf(pdf_url, save_path):
            console.print(f"  [green]✓[/green] Downloaded to {save_path}")
            processed += 1
        else:
            console.print(f"  [red]✗[/red] Failed to download {pdf_url}")

    console.print(f"\n[bold green]Done![/bold green] Processed {processed} papers.")

@app.command()
def extract(
    pdf_path: str = typer.Argument(..., help="Path to the PDF file"),
    allow_mock: bool = typer.Option(False, "--allow-mock", help="Allow mock text if extraction fails")
):
    """
    Extract text from PDF and find biological entities/relationships.
    """
    console.print(f"[bold green]Extracting from:[/bold green] {pdf_path}")
    
    text = extract_text_from_pdf(pdf_path, allow_mock_fallback=allow_mock)
    if not text:
        console.print("[bold red]Failed to extract text.[/bold red]")
        raise typer.Exit(1)
        
    result = extract_relationships(text)
    console.print(f"  [green]✓[/green] Extracted {len(result.entities)} entities and {len(result.relationships)} relationships.")
    
    # Store result for graph command (or just print for now)
    for rel in result.relationships:
        console.print(f"    - {rel.source_entity} [dim]{rel.relationship_type}[/dim] {rel.target_entity}")

@app.command()
def graph(
    pdf_path: str = typer.Argument(..., help="Path to the PDF file to process and insert")
):
    """
    Process a PDF and insert its knowledge into the Neo4j graph.
    """
    console.print(f"[bold green]Graph Ingestion for:[/bold green] {pdf_path}")
    
    text = extract_text_from_pdf(pdf_path)
    if not text:
        console.print("[bold red]Failed to extract text.[/bold red]")
        raise typer.Exit(1)
        
    result = extract_relationships(text)
    
    driver = get_neo4j_driver()
    if not driver:
        console.print("[bold red]Failed to connect to Neo4j.[/bold red]")
        raise typer.Exit(1)
        
    insert_extraction_result(driver, result)
    driver.close()
    console.print("[bold green]✓ Graph updated successfully![/bold green]")

@app.command()
def hypothesis(
    output: str = typer.Option("output/hypotheses", help="Directory for reports")
):
    """
    Query the graph for missing links and evaluate new hypotheses.
    """
    console.print("[bold green]Searching for novel hypotheses...[/bold green]")
    
    driver = get_neo4j_driver()
    if not driver:
        console.print("[bold red]Failed to connect to Neo4j.[/bold red]")
        raise typer.Exit(1)
        
    links = find_missing_links(driver)
    if not links:
        console.print("[yellow]No missing links found in the current graph.[/yellow]")
        return

    for i, link in enumerate(links):
        console.print(f"\n[bold cyan]Hypothesis {i+1}:[/bold cyan] {link['source']} -> {link['target']}")
        eval_result = evaluate_hypothesis(link)
        
        if eval_result.is_plausible:
            console.print(f"  [green]Plausible![/green] (Novelty: {eval_result.novelty_score}/10)")
            report_path = os.path.join(output, f"hypothesis_{i+1}.md")
            generate_markdown_report(link, eval_result, report_path)
            console.print(f"  Report saved to: {report_path}")
        else:
            console.print("  [red]Not plausible[/red] based on LLM reasoning.")

    driver.close()

@app.command()
def setup():
    """
    Interactively set up your VitaGraph AI configuration.
    """
    console.print(Panel.fit(
        "[bold cyan]VitaGraph AI Setup[/bold cyan]\n"
        "Configure your API keys and database connection.",
        border_style="cyan"
    ))

    current_config = config_manager.load()

    gemini_key = Prompt.ask(
        "Enter your Google Gemini API Key",
        default=current_config.gemini_api_key or "",
        password=True
    )
    
    neo4j_uri = Prompt.ask(
        "Enter your Neo4j URI",
        default=current_config.neo4j_uri or "bolt://localhost:7687"
    )
    
    neo4j_user = Prompt.ask(
        "Enter your Neo4j Username",
        default=current_config.neo4j_user or "neo4j"
    )
    
    neo4j_password = Prompt.ask(
        "Enter your Neo4j Password",
        default=current_config.neo4j_password or "password",
        password=True
    )

    new_config = Config(
        gemini_api_key=gemini_key,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password
    )

    config_manager.save(new_config)
    console.print("\n[bold green]✓ Configuration saved successfully![/bold green]")
    console.print(f"Settings stored in: [dim]{config_manager.config_file}[/dim]\n")

@app.callback()
def main():
    """
    VitaGraph AI - Autonomous Research Agent for Longevity
    """
    pass

if __name__ == "__main__":
    app()
