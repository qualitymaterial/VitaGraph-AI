from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.text import Text
from datetime import datetime

class ResearchDashboard:
    """
    Rich terminal dashboard for visualizing the Research Agent's progress.
    """
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self._init_layout()
        
    def _init_layout(self):
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        self.layout["body"].split_row(
            Layout(name="status", ratio=1),
            Layout(name="log", ratio=2)
        )

    def get_header(self, topic: str):
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            "[bold cyan]VitaGraph AI[/bold cyan]",
            f"[bold white]Topic: {topic}[/bold white]",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        return Panel(grid, style="white on blue")

    def get_status_panel(self, stage: str, progress: int):
        table = Table.grid(padding=1)
        table.add_row("[bold]Current Stage:[/bold]", f"[cyan]{stage}[/cyan]")
        
        # A simple visual progress bar string
        bar = "█" * (progress // 10) + "░" * (10 - (progress // 10))
        table.add_row("[bold]Progress:[/bold]", f"[green]{bar}[/green] {progress}%")
        
        return Panel(table, title="System Status", border_style="cyan")

    def get_log_panel(self, messages: list):
        log_text = Text()
        for msg in messages[-15:]: # Show last 15 messages
            log_text.append(f"{msg}\n")
        return Panel(log_text, title="Research Logs", border_style="green")

    def display_static(self, topic: str, stage: str, progress: int, messages: list):
        """Standard static update."""
        self.layout["header"].update(self.get_header(topic))
        self.layout["status"].update(self.get_status_panel(stage, progress))
        self.layout["log"].update(self.get_log_panel(messages))
        self.console.clear()
        self.console.print(self.layout)
