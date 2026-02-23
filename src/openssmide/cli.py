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
from .config import load_config, AVAILABLE_MODELS, save_config
from .voice import quick_voice_input

app = typer.Typer(help="OpenSS: AI-powered screenshot analysis and chat.")
console = Console()
CONFIG = load_config()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


def _read_env() -> dict:
    """Read the .env file into a dict."""
    if not ENV_PATH.exists():
        return {}
    pairs = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            pairs[k.strip()] = v.strip()
    return pairs


def _write_env(pairs: dict):
    """Write a dict back to .env."""
    lines = [f"{k}={v}" for k, v in pairs.items() if v]
    lines.append("")
    ENV_PATH.write_text("\n".join(lines))


def _run_setup():
    """Prompt for API key and optional MongoDB URI, write to .env."""
    console.print()
    console.print("  [bold green]● OpenSS Setup[/bold green]")
    console.print("  ───────────────────")
    console.print()
    console.print(f"  Credentials will be stored in:")
    console.print(f"  [dim]{ENV_PATH}[/dim]")
    console.print()

    api_key = Prompt.ask("  [bold]OpenAI API Key[/bold]").strip()
    if not api_key:
        console.print("  [red]✗ API key is required.[/red]")
        raise typer.Exit(1)

    mongo = Prompt.ask(
        "  [bold]MongoDB URI[/bold] [dim](optional, press Enter to skip)[/dim]",
        default="",
    ).strip()

    env = _read_env()
    env["OPENAI_API_KEY"] = api_key
    if mongo:
        env["MONGO_URI"] = mongo
    _write_env(env)

    os.environ["OPENAI_API_KEY"] = api_key
    if mongo:
        os.environ["MONGO_URI"] = mongo

    console.print()
    console.print("  [green]✓ Saved![/green] You're ready to go.")
    console.print("  Run: [bold]openssmide capture[/bold]")
    console.print()


@app.command()
def setup():
    """Set up your OpenAI API key (and optional MongoDB URI)."""
    _run_setup()


@app.command()
def apikey():
    """Change your OpenAI API key."""
    env = _read_env()
    current = env.get("OPENAI_API_KEY", "")
    masked = current[:6] + "..." + current[-4:] if len(current) > 10 else "(not set)"

    console.print()
    console.print(f"  Current key: [dim]{masked}[/dim]")
    new_key = Prompt.ask("  [bold]New OpenAI API Key[/bold]").strip()
    if not new_key:
        console.print("  [yellow]No change.[/yellow]")
        return
    env["OPENAI_API_KEY"] = new_key
    _write_env(env)
    os.environ["OPENAI_API_KEY"] = new_key
    console.print("  [green]✓ API key updated.[/green]")
    console.print()


@app.command()
def mongo():
    """Set or change your MongoDB URI."""
    env = _read_env()
    current = env.get("MONGO_URI", "")

    console.print()
    if current:
        console.print(f"  Current URI: [dim]{current}[/dim]")
    else:
        console.print("  MongoDB URI: [dim](not set)[/dim]")

    new_uri = Prompt.ask(
        "  [bold]MongoDB URI[/bold] [dim](blank to clear)[/dim]",
        default="",
    ).strip()

    if new_uri:
        env["MONGO_URI"] = new_uri
    elif "MONGO_URI" in env:
        del env["MONGO_URI"]

    _write_env(env)
    if new_uri:
        os.environ["MONGO_URI"] = new_uri
        console.print("  [green]✓ MongoDB URI updated.[/green]")
    else:
        os.environ.pop("MONGO_URI", None)
        console.print("  [green]✓ MongoDB URI cleared.[/green]")
    console.print()


@app.command()
def uninstall():
    """Remove OpenSS from your system."""
    import shutil

    console.print()
    console.print("  [bold red]● OpenSS Uninstall[/bold red]")
    console.print("  ───────────────────")
    console.print()
    console.print(f"  This will remove:")
    console.print(f"  [dim]  • {PROJECT_ROOT}[/dim]")
    console.print(f"  [dim]  • ~/bin/openssmide symlink[/dim]")
    console.print()

    confirm = Prompt.ask("  [bold]Are you sure?[/bold] (yes/no)", default="no").strip().lower()
    if confirm not in ("yes", "y"):
        console.print("  [yellow]Cancelled.[/yellow]")
        return

    # Remove symlink
    symlink = Path.home() / "bin" / "openssmide"
    if symlink.exists() or symlink.is_symlink():
        symlink.unlink()
        console.print("  [dim]✓ Removed ~/bin/openssmide[/dim]")

    # Remove install dir (only if it's ~/.openss — don't nuke a dev checkout)
    install_dir = Path.home() / ".openss"
    if PROJECT_ROOT == install_dir and install_dir.exists():
        shutil.rmtree(install_dir)
        console.print(f"  [dim]✓ Removed {install_dir}[/dim]")
    else:
        console.print(f"  [dim]⚠ Skipped {PROJECT_ROOT} (not a standard install)[/dim]")

    console.print()
    console.print("  [green]✓ OpenSS has been uninstalled.[/green]")
    console.print()


SKIP_SETUP_CMDS = ("setup", "update", "uninstall", "apikey", "mongo")


@app.callback(invoke_without_command=True)
def _welcome(ctx: typer.Context):
    if ctx.invoked_subcommand is not None:
        # Auto-trigger setup if .env is missing (except for management commands)
        if not ENV_PATH.exists() and ctx.invoked_subcommand not in SKIP_SETUP_CMDS:
            console.print()
            console.print("  [yellow]First-time setup required.[/yellow]")
            _run_setup()
        return

    # If no command given, check for .env first
    if not ENV_PATH.exists():
        _run_setup()
        return

    from rich.panel import Panel

    title = "[bold green]Welcome to OpenSS[/bold green]"
    body = (
        "[bold]What it does[/bold]\n"
        "Capture a Chrome window, extract text with macOS OCR, and answer with GPT.\n\n"
        "[bold]Commands[/bold]\n"
        "`openssmide capture`  Capture active Chrome window and answer\n"
        "`openssmide voice`    Ask by voice (native macOS speech-to-text)\n"
        "`openssmide model`    Switch AI models (GPT-4o, mini, etc.)\n"
        "`openssmide update`   Pull latest code and update dependencies\n\n"
        "[bold]Docs[/bold]\n"
        "Interfaces: `INTERFACES.md`"
    )
    console.print(Panel(body, title=title, border_style="green"))

    choice = Prompt.ask(
        "[bold blue]Start[/bold blue] (capture/voice/model/update/exit)",
        default="capture",
    ).strip().lower()
    if choice in ("capture", "c"):
        ctx.invoke(capture, title=None, chat=True, voice=False)
    elif choice in ("voice", "v"):
        ctx.invoke(voice, duration=5, chat=True)
    elif choice in ("model", "m"):
        ctx.invoke(model)
    elif choice in ("update", "u"):
        ctx.invoke(update)
    else:
        return

@app.command()
def model():
    """Switch between different AI models."""
    from rich.table import Table
    table = Table(title="Available OpenAI Models")
    table.add_column("#", style="cyan")
    table.add_column("Model ID", style="magenta")
    table.add_column("Description", style="green")

    for i, m in enumerate(AVAILABLE_MODELS, 1):
        table.add_row(str(i), m["id"], m["desc"])

    console.print(table)
    choice = Prompt.ask("Select model number", choices=[str(i) for i in range(1, len(AVAILABLE_MODELS) + 1)])
    selected = AVAILABLE_MODELS[int(choice) - 1]

    cfg = load_config()
    cfg["model"] = selected["id"]
    save_config(cfg)
    console.print(f"[bold green]Switched to {selected['name']}![/bold green]")


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
    try:
        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Updating OpenSS", total=100)

            progress.update(task, completed=5)
            subprocess.run(
                ["git", "-C", str(root), "pull", "origin", "main"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            progress.update(task, completed=50)

            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(root / "requirements.txt")],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            progress.update(task, completed=100)

        console.print("[bold green]Update complete.[/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Update failed:[/red] {e}")

if __name__ == "__main__":
    app()
