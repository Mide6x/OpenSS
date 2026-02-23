import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.status import Status
from rich.prompt import Prompt, Confirm
import os
import time
from pathlib import Path
from bson import ObjectId

from ss_ai import take_screenshot_and_analyze, build_context, ask_followup, extract_first_code_block, copy_to_clipboard
from ss_shell import load_context, ask_llm, list_sessions, open_latest_session, interactive_chat
from db import add_message
from config import load_config

app = typer.Typer(help="OpenSS: AI-powered screenshot analysis and chat.")
console = Console()
CONFIG = load_config()

def handle_autocopy(text: str):
    if CONFIG.get("autocopy", False):
        code_block = extract_first_code_block(text)
        mode = CONFIG.get("autocopy_mode", "answer")
        
        payload = text
        if mode == "code" and code_block:
            payload = code_block
        elif mode == "answer":
            payload = text
            
        if payload:
            copy_to_clipboard(payload)
            msg = "Whole answer copied" if mode == "answer" else "Code snippet copied"
            return msg
    return None

@app.command()
def capture(
    title: str = typer.Option(None, "--title", "-t", help="Session title"),
    chat: bool = typer.Option(True, "--chat/--no-chat", help="Enter interactive chat after capture")
):
    """Capture a screenshot, analyze it with AI, and optionally start a chat."""
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Error: OPENAI_API_KEY environment variable not set.[/red]")
        raise typer.Exit(1)

    with Status("[bold blue]Capturing and analyzing...", console=console) as status:
        session_id, result = take_screenshot_and_analyze(title)
        
    if not session_id:
        console.print(f"[red]{result}[/red]")
        return

    text, ans, img = result

    console.print(Panel(Markdown(ans), title="AI Analysis", border_style="green"))

    # Explicit Code Display
    code_block = extract_first_code_block(ans)
    if code_block:
        console.print(Panel(code_block, title="Extracted Code", border_style="bold yellow"))

    # Handle Autocopy
    msg = handle_autocopy(ans)
    if msg:
        console.print(f"[dim italic]({msg} to clipboard)[/dim italic]")

    if chat:
        console.print("\n[bold]Entering follow-up chat. Press Ctrl+C or Enter on empty line to exit.[/bold]")
        interactive_chat(session_id)

@app.command()
def chat(
    session_id: str = typer.Option(None, "--id", "-i", help="Session ID to open")
):
    """Open an existing session for chat."""
    if not session_id:
        latest = open_latest_session()
        if not latest:
            console.print("[yellow]No sessions found. Try 'capture' first.[/yellow]")
            return
        current_id = latest
    else:
        try:
            current_id = ObjectId(session_id)
        except Exception:
            console.print(f"[red]Invalid session ID: {session_id}[/red]")
            return

    console.print(f"[bold blue]Resuming session {current_id}[/bold blue]")
    interactive_chat(current_id)

@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of sessions to show")
):
    """Show history of analysis sessions."""
    sessions = list_sessions(limit)
    if not sessions:
        console.print("[yellow]No history found.[/yellow]")
        return

    table = Table(title="Recent Sessions")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("Last Active", style="green")

    for s in sessions:
        table.add_row(str(s["_id"]), s["title"], s["last_active"].strftime("%Y-%m-%d %H:%M:%S"))

    console.print(table)

@app.command()
def config(
    key: str = typer.Argument(None, help="Key to update"),
    value: str = typer.Argument(None, help="New value for the key")
):
    """View or update configuration."""
    import json
    config_path = Path("/Users/nolimitmide/Desktop/OpenSS/config.json")
    
    if key and value:
        # Update config
        try:
            current_config = json.loads(config_path.read_text())
            # Try to parse value as int or bool if possible
            if value.lower() == "true": val = True
            elif value.lower() == "false": val = False
            elif value.isdigit(): val = int(value)
            else: val = value
            
            current_config[key] = val
            config_path.write_text(json.dumps(current_config, indent=4))
            console.print(f"[green]Updated {key} to {val}[/green]")
        except Exception as e:
            console.print(f"[red]Error updating config: {e}[/red]")
        return

    table = Table(title="OpenSS Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    for k, v in CONFIG.items():
        table.add_row(k, str(v))

    console.print(table)
    console.print("\n[dim]To update use: openssmide config <key> <value>[/dim]")

if __name__ == "__main__":
    app()
