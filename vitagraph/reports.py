from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from datetime import datetime

class ResearchDashboard:
    """
    Claude-grade terminal dashboard for visualizing the Research Agent's discovery process.
    """
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.logs = []
        self.discoveries = []
        self.stats = {"entities": 0, "relations": 0, "papers": 0}
        self.current_paper = "Initializing Oracle..."
        self.progress_value = 0
        self._init_layout()
        
    def _init_layout(self):
        self.layout.split_column(
            Layout(name="header", size=4),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="sidebar", size=30),
            Layout(name="content", ratio=1)
        )
        self.layout["content"].split_column(
            Layout(name="status", size=10),
            Layout(name="feed", ratio=1)
        )

    def update_header(self, topic: str):
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        
        title = Text.assemble(
            (" ◈ VITAGRAPH ", "bold white on magenta"),
            (" ORACLE ", "bold magenta on white"),
            (f"  SEARCHING ARCHIVE: {topic.upper()}", "bold cyan")
        )
        
        grid.add_row(
            title,
            f"[dim]{datetime.now().strftime('%H:%M:%S')} | v0.1.0[/dim]"
        )
        return Panel(grid, style="white", border_style="magenta")

    def update_sidebar(self):
        table = Table.grid(padding=(0, 1))
        table.add_row("[bold magenta]KNOWLEDGE BASE[/bold magenta]")
        table.add_row(f"[cyan]Papers:[/cyan] {self.stats['papers']}")
        table.add_row(f"[cyan]Entities:[/cyan] {self.stats['entities']}")
        table.add_row(f"[cyan]Relations:[/cyan] {self.stats['relations']}")
        table.add_row("")
        table.add_row("[bold green]RECENT ACTORS[/bold green]")
        
        # Show unique entities found in this session
        seen = set()
        for d in reversed(self.discoveries):
            if d.get('type') in ["Compound", "Target", "Pathway"] and d['name'] not in seen:
                table.add_row(f"• [dim]{d['name'][:20]}[/dim]")
                seen.add(d['name'])
                if len(seen) > 8: break
                
        return Panel(table, title="[bold white]SYSTEM STATE[/bold white]", border_style="dim magenta")

    def update_status(self, stage: str):
        table = Table.grid(padding=1)
        table.add_row("[bold cyan]ACTIVE STAGE:[/bold cyan]", f"[white]{stage.upper()}[/white]")
        table.add_row("[bold cyan]READING:[/bold cyan]     ", f"[italic white]{self.current_paper[:50]}...[/italic white]")
        
        # High-end progress bar
        done = min(self.progress_value // 4, 25)
        bar = "━" * done + ("╸" if done < 25 else "") + " " * max(0, 25 - done - 1)
        table.add_row("[bold cyan]PIPELINE:[/bold cyan]   ", f"[magenta][{bar}][/magenta] [bold]{self.progress_value}%[/bold]")
        
        return Panel(table, title="[bold cyan]ORCHESTRATOR[/bold cyan]", border_style="cyan")

    def update_feed(self):
        table = Table(box=None, expand=True, padding=(0, 1))
        table.add_column("Discovery Event", style="green", ratio=1)
        table.add_column("Type", style="dim white", justify="right")
        
        for d in self.discoveries[-12:]:
            icon = "✨" if "→" in d['name'] else "🔬"
            table.add_row(f"{icon} {d['name']}", d.get('type', 'Unknown'))
            
        return Panel(table, title="[bold green]DISCOVERY STREAM[/bold green]", border_style="green")

    def render(self, topic: str, stage: str):
        self.layout["header"].update(self.update_header(topic))
        self.layout["sidebar"].update(self.update_sidebar())
        self.layout["status"].update(self.update_status(stage))
        self.layout["feed"].update(self.update_feed())
        self.layout["footer"].update(Panel(
            f"[dim]SYSTEM LOG: {self.logs[-1] if self.logs else 'Listening...'} [/dim]", 
            border_style="dim"
        ))
        return self.layout
