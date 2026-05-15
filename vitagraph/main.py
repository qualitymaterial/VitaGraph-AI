import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from .config import config_manager, Config

app = typer.Typer(
    name="vitagraph",
    help="VitaGraph AI: Autonomous Longevity Research CLI",
    add_completion=False,
)
console = Console()

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
