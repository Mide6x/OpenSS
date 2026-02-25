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
import readline
from pathlib import Path
from bson import ObjectId

from .ss_ai import (
    take_screenshot_and_analyze,
    build_context,
    ask_followup,
    ask_prompt,
    extract_first_code_block,
    copy_to_clipboard,
    general_ask,
    handle_ai_response,
    require_api_key,
)
from .ss_shell import load_context, ask_llm, list_sessions, open_latest_session, interactive_chat
from .db import add_message, create_session
from .config import load_config, AVAILABLE_MODELS, save_config
from .voice import quick_voice_input
from .word_automation import (
    open_document,
    read_active_document,
    write_active_document,
    save_active_document,
)

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
    """Prompt for provider API keys and optional MongoDB URI, write to .env."""
    console.print()
    console.print("  [bold green]● OpenSS Setup[/bold green]")
    console.print("  ───────────────────")
    console.print()
    console.print(f"  Credentials will be stored in:")
    console.print(f"  [dim]{ENV_PATH}[/dim]")
    console.print()

    openai_key = Prompt.ask("  [bold]OpenAI API Key[/bold] [dim](press Enter to skip if using Anthropic)[/dim]", default="").strip()
    anthropic_key = Prompt.ask("  [bold]Anthropic API Key[/bold] [dim](press Enter to skip if using OpenAI)[/dim]", default="").strip()
    
    if not openai_key and not anthropic_key:
        console.print("  [red]✗ At least one API key (OpenAI or Anthropic) is required.[/red]")
        raise typer.Exit(1)

    mongo = Prompt.ask(
        "  [bold]MongoDB URI[/bold] [dim](optional, press Enter to skip)[/dim]",
        default="",
    ).strip()

    env = _read_env()
    if openai_key:
        env["OPENAI_API_KEY"] = openai_key
    if anthropic_key:
        env["ANTHROPIC_API_KEY"] = anthropic_key
    if mongo:
        env["MONGO_URI"] = mongo
    _write_env(env)

    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key
    if anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key
    if mongo:
        os.environ["MONGO_URI"] = mongo

    console.print()
    console.print("  [green]✓ Saved![/green] You're ready to go.")
    console.print("  Run: [bold]openssmide capture[/bold]")
    console.print()


@app.command()
def setup():
    """Set up OpenAI/Anthropic API keys (and optional MongoDB URI)."""
    _run_setup()


@app.command()
def apikey():
    """Change your OpenAI or Anthropic API keys."""
    env = _read_env()
    
    current_openai = env.get("OPENAI_API_KEY", "")
    masked_openai = current_openai[:6] + "..." + current_openai[-4:] if len(current_openai) > 10 else "(not set)"
    
    current_anthropic = env.get("ANTHROPIC_API_KEY", "")
    masked_anthropic = current_anthropic[:6] + "..." + current_anthropic[-4:] if len(current_anthropic) > 10 else "(not set)"

    console.print()
    console.print(f"  Current OpenAI key: [dim]{masked_openai}[/dim]")
    new_openai = Prompt.ask("  [bold]New OpenAI API Key[/bold] [dim](leave blank to keep current)[/dim]", default="").strip()
    
    console.print(f"  Current Anthropic key: [dim]{masked_anthropic}[/dim]")
    new_anthropic = Prompt.ask("  [bold]New Anthropic API Key[/bold] [dim](leave blank to keep current)[/dim]", default="").strip()
    
    updated = False
    if new_openai:
        env["OPENAI_API_KEY"] = new_openai
        os.environ["OPENAI_API_KEY"] = new_openai
        updated = True
        
    if new_anthropic:
        env["ANTHROPIC_API_KEY"] = new_anthropic
        os.environ["ANTHROPIC_API_KEY"] = new_anthropic
        updated = True

    if updated:
        _write_env(env)
        console.print("  [green]✓ API key(s) updated.[/green]")
    else:
        console.print("  [yellow]No changes made.[/yellow]")
    console.print()


@app.command()
def anthropic():
    """Change your Anthropic API key."""
    env = _read_env()
    current = env.get("ANTHROPIC_API_KEY", "")
    masked = current[:6] + "..." + current[-4:] if len(current) > 10 else "(not set)"

    console.print()
    console.print(f"  Current key: [dim]{masked}[/dim]")
    new_key = Prompt.ask("  [bold]New Anthropic API Key[/bold]").strip()
    if not new_key:
        console.print("  [yellow]No change.[/yellow]")
        return
    env["ANTHROPIC_API_KEY"] = new_key
    _write_env(env)
    os.environ["ANTHROPIC_API_KEY"] = new_key
    console.print("  [green]✓ Anthropic API key updated.[/green]")
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


SKIP_SETUP_CMDS = ("setup", "update", "uninstall", "apikey", "anthropic", "mongo")


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
        "Capture a Chrome, PowerPoint, or Word window, extract text with macOS OCR, and answer with GPT.\n\n"
        "[bold]Commands[/bold]\n"
        "`openssmide capture`  Capture active window (Chrome/PowerPoint/Word) and answer\n"
        "`openssmide word`     Read/ask/edit active Microsoft Word document\n"
        "`openssmide voice`    Ask by voice (native macOS speech-to-text)\n"
        "`openssmide model`    Switch AI models (OpenAI/Claude)\n"
        "`openssmide update`   Pull latest code and update dependencies\n\n"
        "[bold]Docs[/bold]\n"
        "Interfaces: `INTERFACES.md`"
    )
    console.print(Panel(body, title=title, border_style="green"))

    choice = Prompt.ask(
        "[bold blue]Start[/bold blue] (capture/word/voice/model/update/exit)",
        default="capture",
    ).strip().lower()
    if choice in ("capture", "c"):
        ctx.invoke(capture, title=None, chat=True, voice=False, target=None, full_slide=False)
    elif choice in ("word", "w"):
        ctx.invoke(word, action="read", instruction=None, text=None, file=None)
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
    table = Table(title="Available AI Models")
    table.add_column("#", style="cyan")
    table.add_column("Provider", style="yellow")
    table.add_column("Model ID", style="magenta")
    table.add_column("Description", style="green")

    for i, m in enumerate(AVAILABLE_MODELS, 1):
        table.add_row(str(i), m.get("provider", "openai"), m["id"], m["desc"])

    console.print(table)
    choice = Prompt.ask("Select model number", choices=[str(i) for i in range(1, len(AVAILABLE_MODELS) + 1)])
    selected = AVAILABLE_MODELS[int(choice) - 1]
    env = _read_env()
    provider = selected.get("provider", "openai")
    if provider == "anthropic" and not env.get("ANTHROPIC_API_KEY"):
        console.print("[red]Missing ANTHROPIC_API_KEY. Run: openssmide anthropic (or openssmide setup).[/red]")
        return
    if provider == "openai" and not env.get("OPENAI_API_KEY"):
        console.print("[red]Missing OPENAI_API_KEY. Run: openssmide apikey (or openssmide setup).[/red]")
        return

    cfg = load_config()
    cfg["model"] = selected["id"]
    save_config(cfg)
    console.print(f"[bold green]Switched to {selected['name']}![/bold green]")


@app.command()
def capture(
    title: str = typer.Option(None, "--title", "-t", help="Session title"),
    chat: bool = typer.Option(True, "--chat/--no-chat", help="Enter interactive chat after capture"),
    voice: bool = typer.Option(False, "--voice", "-v", help="Use voice input for initial question (not applicable to screenshot OCR)"),
    target: str = typer.Option(None, "--target", "-a", help="Capture target: chrome, powerpoint, or word"),
    full_slide: bool = typer.Option(
        False,
        "--full-slide/--window",
        help="When target=powerpoint, require Slide Show mode to capture the full slide area.",
    ),
):
    """Capture a screenshot, analyze it with AI, and optionally start a chat."""
    cfg = load_config()
    if target is None:
        from .capture_rules import detect_active_target
        capture_target = detect_active_target()
    else:
        capture_target = target.strip().lower()

    if capture_target not in ("chrome", "powerpoint", "word"):
        console.print("[red]Invalid --target. Use 'chrome', 'powerpoint', or 'word'.[/red]")
        return

    # Handle Voice Input for Question
    voice_question = None
    if voice:
        console.print("[bold green]Listening for your question (5s)...[/bold green]")
        voice_question, err = quick_voice_input(5)
        if err:
            console.print(f"[red]Error: {err}[/red]")
        elif voice_question:
            console.print(f"[bold blue]Question:[/bold blue] {voice_question}")

    with Status(f"[bold blue]Capturing {capture_target} and analyzing...", console=console) as status:
        session_id, result = take_screenshot_and_analyze(
            title,
            target=capture_target,
            full_slide=full_slide,
        )
        
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
def word(
    action: str = typer.Option(
        "read",
        "--action",
        "-a",
        help="Action: read, ask, write, edit",
    ),
    instruction: str = typer.Option(
        None,
        "--instruction",
        "-i",
        help="Question (ask) or edit instruction (edit).",
    ),
    text: str = typer.Option(
        None,
        "--text",
        help="Direct text used by --action write (replaces active document content).",
    ),
    file: str = typer.Option(
        None,
        "--file",
        "-f",
        help="Optional .docx file path to open in Word before action.",
    ),
):
    """Read, ask, write, or AI-edit the active Microsoft Word document."""
    action = (action or "read").strip().lower()
    if action not in ("read", "ask", "write", "edit"):
        console.print("[red]Invalid --action. Use: read, ask, write, edit.[/red]")
        return

    if file:
        try:
            open_document(Path(file))
            time.sleep(0.25)
        except Exception as e:
            console.print(f"[red]Failed to open file in Word: {e}[/red]")
            return

    try:
        title, doc_text = read_active_document()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        return

    cfg = load_config()
    max_chars = int(cfg.get("max_word_chars", 40000))
    if len(doc_text) > max_chars and action in ("ask", "edit"):
        console.print(
            f"[red]Document too large ({len(doc_text)} chars). Increase max_word_chars (current {max_chars}) or shorten document.[/red]"
        )
        return

    if action == "read":
        console.print(Panel(Markdown(doc_text or "_(empty document)_"), title=f"Word: {title}", border_style="cyan"))
        return

    if action == "ask":
        if not instruction:
            console.print("[red]Missing --instruction for --action ask.[/red]")
            return
        require_api_key()
        prompt = cfg["prompt_word_question"].format(
            doc_title=title,
            doc_text=doc_text,
            question=instruction,
        )
        with Status("[dim]Analyzing document...[/dim]", console=console):
            ans = ask_prompt(prompt, model_id=cfg["model"])
        console.print(Panel(Markdown(ans), title="Word Analysis", border_style="green"))
        return

    if action == "write":
        if text is None:
            console.print("[red]Missing --text for --action write.[/red]")
            return
        try:
            write_active_document(text)
        except Exception as e:
            console.print(f"[red]Write failed: {e}[/red]")
            return
        console.print("[green]Word document updated.[/green]")
        return
    if action == "edit":
        if not instruction:
            console.print("[red]Missing --instruction for --action edit.[/red]")
            return
        require_api_key()
        prompt = cfg["prompt_word_edit"].format(
            doc_title=title,
            doc_text=doc_text,
            instruction=instruction,
        )
        with Status("[dim]Editing document with AI...[/dim]", console=console):
            revised_text = ask_prompt(prompt, model_id=cfg["model"])
        if not revised_text.strip():
            console.print("[red]AI returned empty content; edit aborted.[/red]")
            return
        try:
            write_active_document(revised_text)
        except Exception as e:
            console.print(f"[red]Edit failed: {e}[/red]")
            return
        console.print("[green]Word document edited and applied.[/green]")

@app.command()
def write(
    chat: bool = typer.Option(True, "--chat/--no-chat", help="Enter interactive chat to edit the document after writing")
):
    """Interactively prompt the AI to generate content and write it into the active Microsoft Word document."""
    try:
        # Just check if Word is running/active document exists.
        read_active_document()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        return
        
    prompt_text = Prompt.ask("[bold blue]What do you want to write?[/bold blue]").strip()
    if not prompt_text:
        console.print("[red]Input cannot be empty.[/red]")
        return

    with Status("[dim]Generating content...", console=console):
        # We can use the configured general prompt but modify it slightly for purely writing tasks
        cfg = load_config()
        # Direct instruction ensures it only returns the requested text without chatty filler
        instruction = f"Write the following content directly without markdown formatting (unless specified), conversational filler, or intro/outro text:\n\n{prompt_text}"
        ans = ask_prompt(instruction, cfg["model"])
        
    handle_ai_response(ans, console)
    
    try:
        write_active_document(ans)
        console.print("[green]✓ Output successfully written to the active Word document.[/green]")
    except Exception as e:
        console.print(f"[red]Failed to write to Word: {e}[/red]")
        return

    # Create session
    title = f"Word Write: {prompt_text[:30]}..."
    session_id = create_session(title)
    add_message(session_id, "user", prompt_text)
    add_message(session_id, "assistant", ans)

    if chat:
        console.print("\n[bold]Entering follow-up chat to edit the document. Press Ctrl+C or Enter on empty line to exit.[/bold]")
        interactive_chat(session_id, auto_write_word=True)

@app.command()
def summarize():
    """Extract text from the active Microsoft Word document and summarize it using AI."""
    try:
        title, doc_text = read_active_document()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        return

    if not doc_text.strip():
        console.print("[red]The active Word document is empty.[/red]")
        return

    cfg = load_config()
    max_chars = int(cfg.get("max_word_chars", 40000))
    if len(doc_text) > max_chars:
        console.print(
            f"[red]Document too large ({len(doc_text)} chars). Increase max_word_chars (current {max_chars}) or shorten document.[/red]"
        )
        return

    with Status(f"[dim]Summarizing '{title}'...", console=console):
        instruction = f"Please provide a comprehensive summary of the following document:\n\n{doc_text}"
        ans = ask_prompt(instruction, cfg["model"])

    console.print(f"\n[bold green]Summary for {title}:[/bold green]")
    handle_ai_response(ans, console)

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
