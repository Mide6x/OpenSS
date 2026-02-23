import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.status import Status
from rich.prompt import Prompt, Confirm
import os
import sys
import subprocess
import time
from pathlib import Path
from bson import ObjectId

from .ss_ai import (
    take_screenshot_and_analyze,
    build_context,
    ask_followup,
    extract_first_code_block,
    copy_to_clipboard,
    general_ask,
    handle_ai_response,
)
from .ss_shell import load_context, ask_llm, list_sessions, open_latest_session, interactive_chat
from .db import add_message, create_session
from .config import load_config
from .voice import quick_voice_input

app = typer.Typer(help="OpenSS: AI-powered screenshot analysis and chat.")
console = Console()
CONFIG = load_config()


@app.callback(invoke_without_command=True)
def _welcome(ctx: typer.Context):
    if ctx.invoked_subcommand is not None:
        return
    from rich.panel import Panel
    from rich.prompt import Prompt

    title = "[bold green]Welcome to OpenSS[/bold green]"
    body = (
        "[bold]What it does[/bold]\n"
        "Capture a Chrome window, extract text with macOS OCR, and answer with GPT.\n\n"
        "[bold]Commands[/bold]\n"
        "`openssmide capture`  Capture active Chrome window and answer\n"
        "`openssmide voice`    Ask by voice (native macOS speech-to-text)\n"
        "`openssmide update`   Pull latest code and update dependencies\n\n"
        "[bold]Docs[/bold]\n"
        "Interfaces: `INTERFACES.md`"
    )
    console.print(Panel(body, title=title, border_style="green"))

    choice = Prompt.ask(
        "[bold blue]Start[/bold blue] (capture/voice/update/exit)",
        default="capture",
    ).strip().lower()
    if choice in ("capture", "c"):
        ctx.invoke(capture)
    elif choice in ("voice", "v"):
        ctx.invoke(voice)
    elif choice in ("update", "u"):
        ctx.invoke(update)
    else:
        return

@app.command()
def capture(
    title: str = typer.Option(None, "--title", "-t", help="Session title"),
    chat: bool = typer.Option(True, "--chat/--no-chat", help="Enter interactive chat after capture"),
    voice: bool = typer.Option(False, "--voice", "-v", help="Use voice input for initial question (not applicable to screenshot OCR)")
):
    """Capture a screenshot, analyze it with AI, and optionally start a chat."""
    # Handle Voice Input for Question
    voice_question = None
    if voice:
        console.print("[bold green]Listening for your question (5s)...[/bold green]")
        voice_question, err = quick_voice_input(5)
        if err:
            console.print(f"[red]Error: {err}[/red]")
        elif voice_question:
            console.print(f"[bold blue]Question:[/bold blue] {voice_question}")

    with Status("[bold blue]Capturing and analyzing...", console=console) as status:
        session_id, result = take_screenshot_and_analyze(title)
        
    if not session_id:
        console.print(f"[red]{result}[/red]")
        return

    text, ans, img = result
    
    # If we have a voice question, perform a follow-up immediately
    if voice_question:
        with Status("[bold blue]Analyzing voice question...", console=console):
            ctx = build_context(session_id)
            ans = ask_followup(ctx, voice_question)
            add_message(session_id, "user", voice_question)
            add_message(session_id, "assistant", ans)

    handle_ai_response(ans, console)

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
    config_path = Path(__file__).resolve().parents[2] / "config.json"
    
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

@app.command()
def voice(
    duration: int = typer.Option(5, "--duration", "-d", help="Recording duration in seconds"),
    chat: bool = typer.Option(True, "--chat/--no-chat", help="Enter interactive chat after query")
):
    """Voice command: Ask a question verbally and get an AI response. Optionally start a chat."""
    console.print(f"[bold green]Listening for {duration}s...[/bold green]")
    text, err = quick_voice_input(duration)
    if err:
        console.print(f"[red]Error: {err}[/red]")
        return
    if text:
        console.print(f"\n[bold blue]You said:[/bold blue] {text}")
        
        with Status("[dim]Thinking...", console=console):
            ans = general_ask(text)
            
        handle_ai_response(ans, console)
        
        # Create session
        title = f"Voice: {text[:30]}..."
        session_id = create_session(title)
        add_message(session_id, "user", text)
        add_message(session_id, "assistant", ans)

        if chat:
            console.print("\n[bold]Entering follow-up chat. Press Ctrl+C or Enter on empty line to exit.[/bold]")
            interactive_chat(session_id)
    else:
        console.print("[yellow]No speech detected.[/yellow]")

@app.command()
def ask(
    question: str = typer.Argument(None, help="Question to ask (leave blank to read from stdin/paste)"),
    chat: bool = typer.Option(True, "--chat/--no-chat", help="Enter interactive chat after query")
):
    """Directly ask the AI a question (supports multi-line stdin). Optionally start a chat."""
    q = question
    if not q:
        import sys
        if sys.stdin.isatty():
            console.print("[bold yellow]Direct Input Mode:[/bold yellow] Type/paste your question and press [bold]Ctrl+D[/bold] (Mac/Linux) or [bold]Ctrl+Z[/bold] (Windows) to finish.")
        q = sys.stdin.read().strip()
        
    if not q:
        console.print("[red]No question provided.[/red]")
        return

    with Status("[dim]Thinking...", console=console):
        ans = general_ask(q)
        
    handle_ai_response(ans, console)
    
    # Create session
    title = f"Ask: {q[:30]}..."
    session_id = create_session(title)
    add_message(session_id, "user", q)
    add_message(session_id, "assistant", ans)

    if chat:
        console.print("\n[bold]Entering follow-up chat. Press Ctrl+C or Enter on empty line to exit.[/bold]")
        interactive_chat(session_id)


@app.command()
def update():
    """Pull latest code and update dependencies."""
    root = Path(__file__).resolve().parents[2]
    console.print("[bold blue]Updating OpenSS...[/bold blue]")
    try:
        subprocess.run(["git", "-C", str(root), "pull", "origin", "main"], check=True)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(root / "requirements.txt")],
            check=True,
        )
        console.print("[bold green]Update complete.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Update failed:[/red] {e}")

if __name__ == "__main__":
    app()
