import typer
import os
import logging
import readline
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from .config import config_manager, Config
from .core.ingest_rxiv import fetch_biorxiv_api, download_pdf, extract_text_from_pdf
from .core.extract import extract_relationships
from .core.graph import get_neo4j_driver, insert_extraction_result, normalize_entities
from .core.hypothesis import find_missing_links, evaluate_hypothesis, generate_markdown_report
from .agent import ResearchOracle

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

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
    topic: str = typer.Option("", help="Topic keyword to search for"),
    days: int = typer.Option(7, help="Number of days to look back"),
    limit: int = typer.Option(5, help="Limit number of papers"),
    output_dir: Optional[str] = typer.Option(None, help="Directory to save PDFs")
):
    """
    Fetch preprints from bioRxiv API and download PDFs.
    """
    config = config_manager.config
    save_dir = output_dir or config.output_dir
    
    console.print(f"[bold green]Ingesting preprints from bioRxiv API...[/bold green]")
    entries = fetch_biorxiv_api(topic=topic, days=days)
    
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
    topic: str = typer.Option("General Longevity", help="Topic for the report")
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
        driver.close()
        return

    # Generate the professional Markdown report
    report_content = generate_markdown_report(topic, links)
    
    # Save report to the Wiki
    os.makedirs("wiki/Reports", exist_ok=True)
    report_filename = f"discovery_{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = os.path.join("wiki/Reports", report_filename)
    
    with open(report_path, "w") as f:
        f.write(report_content)
    
    console.print(f"\n[bold green]✔ Discovery Report generated:[/bold green] [cyan]{report_path}[/cyan]")
    driver.close()

@app.command()
def papers(
    limit: int = typer.Option(10, help="Number of papers to show")
):
    """
    List all papers that have been successfully ingested into the graph.
    """
    console.print("[bold green]Ingested Papers in Knowledge Graph:[/bold green]")
    
    driver = get_neo4j_driver()
    if not driver:
        console.print("[bold red]Failed to connect to Neo4j.[/bold red]")
        raise typer.Exit(1)
        
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Paper)
            RETURN p.title AS title, p.doi AS doi, p.updated_at AS date
            ORDER BY p.updated_at DESC
            LIMIT $limit
        """, {"limit": limit})
        
        table = Table(title="Recent Research Library")
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("DOI", style="magenta")
        table.add_column("Ingested At", style="dim")
        
        found = False
        for record in result:
            found = True
            from datetime import datetime
            ts = record["date"] / 1000 if record["date"] else 0
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "Unknown"
            table.add_row(record["title"], record["doi"], date_str)
            
        if not found:
            console.print("[yellow]No papers found in the database. Run 'vitagraph research' first.[/yellow]")
        else:
            console.print(table)
            
    driver.close()

@app.command()
def entities(
    type: Optional[str] = typer.Option(None, help="Filter by type (Compound, Target, Pathway, Disease)"),
    limit: int = typer.Option(20, help="Number of entities to show")
):
    """
    List biological entities discovered and stored in the graph.
    """
    console.print("[bold green]Discovered Entities in Knowledge Graph:[/bold green]")
    
    driver = get_neo4j_driver()
    if not driver:
        console.print("[bold red]Failed to connect to Neo4j.[/bold red]")
        raise typer.Exit(1)
        
    with driver.session() as session:
        query = "MATCH (e:Entity)"
        if type:
            query += " WHERE e.type = $type"
        query += " RETURN e.name AS name, e.type AS type ORDER BY e.name LIMIT $limit"
        
        result = session.run(query, {"type": type, "limit": limit})
        
        table = Table(title="Knowledge Base Entities")
        table.add_column("Entity Name", style="cyan")
        table.add_column("Type", style="magenta")
        
        found = False
        for record in result:
            found = True
            table.add_row(record["name"], record["type"] or "Unknown")
            
        if not found:
            console.print("[yellow]No entities found. Start researching to build your graph![/yellow]")
        else:
            console.print(table)
            
    driver.close()

@app.command()
def normalize():
    """
    Merge duplicate entity nodes in the graph caused by name variants or synonym overlap.
    Safe to run at any time — checks for case-insensitive duplicates (mTOR vs MTOR)
    and synonym-based duplicates (rapamycin vs sirolimus if linked via synonyms).
    """
    driver = get_neo4j_driver()
    if not driver:
        console.print("[bold red]Failed to connect to Neo4j.[/bold red]")
        raise typer.Exit(1)

    # Show before stats
    with driver.session() as session:
        before = session.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]

    console.print(f"[dim]Entity count before:[/dim] {before}")
    console.print("[cyan]Scanning for duplicate entities...[/cyan]")

    result = normalize_entities(driver)
    merged = result["merged"]

    with driver.session() as session:
        after = session.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]

    driver.close()

    if merged == 0:
        console.print("[green]✓ Graph is clean — no duplicate entities found.[/green]")
    else:
        console.print(f"[bold green]✓ Merged {merged} duplicate node(s).[/bold green] "
                      f"[dim]{before} → {after} entities[/dim]")


@app.command()
def shell():
    """
    Enter the interactive VitaGraph AI Command Deck.
    """
    readline.parse_and_bind("tab: complete")

    console.print(Panel.fit(
        "[bold magenta]⚡ VITAGRAPH COMMAND DECK[/bold magenta]\n"
        "Type [bold cyan]/help[/bold cyan] to see available commands or [bold cyan]/exit[/bold cyan] to quit.",
        border_style="magenta"
    ))

    while True:
        try:
            cmd_input = Prompt.ask("[bold magenta]vita[/bold magenta] > ").strip()

            if not cmd_input:
                continue

            # Route slash commands
            parts = cmd_input.split(" ", 1)
            base = parts[0].lower()
            args = parts[1].strip() if len(parts) > 1 else ""

            # Expand shortcuts before routing
            shortcuts = {"/r": "/research", "/p": "/papers", "/e": "/entities", "/h": "/hypothesis", "/n": "/normalize", "/s": "/setup", "/q": "/exit"}
            base = shortcuts.get(base, base)

            if base in ["/exit", "/quit", "exit", "quit"]:
                console.print("[dim]Disconnecting from Oracle...[/dim]")
                break

            elif base in ["/help", "/?"]:
                table = Table(title="VitaGraph Command Deck Guide", box=None)
                table.add_column("Command", style="cyan")
                table.add_column("Shortcut", style="dim")
                table.add_column("Description", style="white")
                table.add_row("/research <topic>", "/r", "Start autonomous research on a topic")
                table.add_row("/papers", "/p", "List all ingested papers")
                table.add_row("/entities", "/e", "List all discovered entities")
                table.add_row("/hypothesis", "/h", "Search for new discoveries")
                table.add_row("/normalize", "/n", "Merge duplicate entity nodes in graph")
                table.add_row("/status", "", "Check config and connection health")
                table.add_row("/setup", "/s", "Update configuration")
                table.add_row("/exit", "/q", "Leave the Command Deck")
                console.print(table)

            elif base == "/":
                menu = Table(title="[bold magenta]COMMAND MENU[/bold magenta]", box=None, padding=(0, 2))
                menu.add_column("Shortcut", style="bold cyan")
                menu.add_column("Action", style="white")
                menu.add_column("Description", style="dim")
                menu.add_row("/r <topic>", "Research", "Start a discovery loop")
                menu.add_row("/p", "Library", "List ingested papers")
                menu.add_row("/e", "Actors", "List discovered entities")
                menu.add_row("/h", "Discovery", "Run hypothesis engine")
                menu.add_row("/s", "Setup", "Configure API keys")
                menu.add_row("/q", "Quit", "Exit the deck")
                console.print(Panel(menu, border_style="magenta"))

            elif base == "/research":
                topic = args or Prompt.ask("[cyan]Research topic[/cyan]")
                if topic:
                    oracle = ResearchOracle(console=console)
                    oracle.run_topic_research(topic)

            elif base == "/papers":
                papers()

            elif base == "/entities":
                entities()

            elif base == "/hypothesis":
                hypothesis()

            elif base == "/normalize":
                normalize()

            elif base == "/status":
                status()

            elif base == "/setup":
                setup()

            else:
                console.print(f"[red]Unknown command:[/red] {cmd_input}. Type [cyan]/help[/cyan] for a list.")

        except KeyboardInterrupt:
            console.print("\n[dim]Aborting...[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")

@app.command()
def status():
    """
    Check the health of your VitaGraph configuration and connections.
    """
    config = config_manager.config

    table = Table(title="VitaGraph Status", box=None, padding=(0, 2))
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="white")

    # Gemini API key
    if config.gemini_api_key:
        table.add_row("Gemini API Key", "[green]✓ Configured[/green]")
    else:
        table.add_row("Gemini API Key", "[red]✗ Missing — run 'vitagraph setup'[/red]")

    # Neo4j connection
    driver = get_neo4j_driver()
    if driver:
        table.add_row("Neo4j", f"[green]✓ Connected[/green] [dim]({config.neo4j_uri})[/dim]")
        driver.close()
    else:
        table.add_row("Neo4j", f"[red]✗ Cannot connect[/red] [dim]({config.neo4j_uri})[/dim]")

    # Output dir
    output_exists = os.path.isdir(config.output_dir)
    table.add_row(
        "Output dir",
        f"[green]✓ {config.output_dir}[/green]" if output_exists else f"[yellow]⚠ {config.output_dir} (will be created)[/yellow]"
    )

    console.print(table)


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

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    VitaGraph AI - Autonomous Research Agent for Longevity
    """
    if ctx.invoked_subcommand is None:
        shell()

if __name__ == "__main__":
    app()
