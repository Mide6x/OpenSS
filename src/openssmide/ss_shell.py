import os

from bson import ObjectId
from openai import OpenAI
from dotenv import load_dotenv

from .config import load_config
from .db import add_message, get_session_messages, list_sessions


load_dotenv()
CONFIG = load_config()
MODEL = os.getenv("SS_MODEL", CONFIG["model"])
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

current_session = None


def ask_llm(context: str, question: str) -> str:
    cfg = load_config()
    prompt = cfg["prompt_followup"].format(context=context, question=question)
    r = client.responses.create(model=cfg.get("model", "gpt-4o-mini"), input=prompt)
    return r.output_text.strip()


def print_sessions():
    sessions = list_sessions(20)
    for s in sessions:
        print(f"{s['_id']}  | {s['title']}  | {s['last_active']}")


def load_context(session_id) -> str:
    msgs = get_session_messages(session_id)
    ctx_lines = []
    for m in msgs:
        role = "User" if m["role"] == "user" else "Assistant"
        ctx_lines.append(f"{role}: {m['text']}")
    ctx = "\n".join(ctx_lines)
    max_chars = CONFIG.get("max_context_chars", 8000)
    if len(ctx) > max_chars:
        ctx = ctx[-max_chars:]
    return ctx


def open_latest_session():
    sessions = list_sessions(1)
    if not sessions:
        return None
    return sessions[0]["_id"]


def interactive_chat(session_id):
    from rich.console import Console
    from rich.prompt import Prompt
    from .ss_ai import handle_ai_response
    from .config import AVAILABLE_MODELS, save_config
    import sys
    import select
    import fcntl
    
    console = Console()
    current_session = session_id
    
    console.print("\n[bold green]Chat session active.[/bold green] [dim](Type /v for voice, /m for multiline, /model to switch)[/dim]\n")
    
    while True:
        try:
            q = Prompt.ask("[bold blue]Ask[/bold blue]")
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        if not q:
            break
            
        # Paste detection: Drain everything currently in the buffer
        # We use non-blocking read to get everything lingering in the OS/Terminal buffer
        fd = sys.stdin.fileno()
        old_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        try:
            fcntl.fcntl(fd, fcntl.F_SETFL, old_fl | os.O_NONBLOCK)
            while True:
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    extra = sys.stdin.read(4096)
                    if not extra: break
                    q += extra
                else: break
        except (IOError, select.error):
            pass
        finally:
            fcntl.fcntl(fd, fcntl.F_SETFL, old_fl)

        # Commands
        cmd = q.strip().lower()
        if cmd in ("/v", "/voice"):
            from .voice import quick_voice_input
            console.print("[bold green]Listening (5s)...[/bold green]")
            voice_text, err = quick_voice_input(5)
            if err:
                console.print(f"[red]Error: {err}[/red]")
                continue
            if not voice_text:
                console.print("[yellow]No speech detected.[/yellow]")
                continue
            console.print(f"[bold blue]You said:[/bold blue] {voice_text}")
            q = voice_text
        elif cmd in ("/m", "/multiline"):
            console.print("[bold yellow]Multiline Mode:[/bold yellow] Type your message, then a single [bold].[/bold] on a new line to finish.")
            lines = []
            while True:
                line = sys.stdin.readline()
                if line.strip() == ".":
                    break
                lines.append(line.rstrip("\n"))
            q = "\n".join(lines)
            if not q.strip():
                continue
        elif cmd in ("/model", "/switch"):
            from rich.table import Table
            table = Table(title="Available Models")
            table.add_column("#", style="cyan")
            table.add_column("Model ID", style="magenta")
            table.add_column("Description", style="green")
            for i, m in enumerate(AVAILABLE_MODELS, 1):
                table.add_row(str(i), m["id"], m["desc"])
            console.print(table)
            choice = Prompt.ask("Select model number", choices=[str(i) for i in range(1, len(AVAILABLE_MODELS)+1)])
            selected = AVAILABLE_MODELS[int(choice)-1]
            cfg = load_config()
            cfg["model"] = selected["id"]
            save_config(cfg)
            console.print(f"[bold green]Switched to {selected['name']}![/bold green]\n")
            continue

        with console.status("[dim]Thinking...[/dim]"):
            ctx = load_context(current_session)
            ans = ask_llm(ctx, q)
            
        handle_ai_response(ans, console)
        
        add_message(current_session, "user", q)
        add_message(current_session, "assistant", ans)
        console.print("") # Padding


def main():
    global current_session

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY first")

    print("SS-AI shell. Type /help")

    while True:
        cmd = input(">> ").strip()

        if cmd == "/exit":
            break

        if cmd == "/sessions":
            print_sessions()
            continue

        if cmd == "/latest":
            latest = open_latest_session()
            if not latest:
                print("No sessions found.")
                continue
            current_session = latest
            print("Opened latest session", str(latest))
            continue

        if cmd.startswith("/open "):
            sid = cmd.split(" ", 1)[1].strip()
            current_session = ObjectId(sid)
            print("Opened session", sid)
            continue

        if cmd.startswith("/ask "):
            if not current_session:
                print("Open session first with /open <id>")
                continue

            q = cmd.split(" ", 1)[1].strip()
            ctx = load_context(current_session)
            ans = ask_llm(ctx, q)

            print("\n", ans, "\n")
            add_message(current_session, "user", q)
            add_message(current_session, "assistant", ans)
            continue

        if cmd == "/follow":
            latest = open_latest_session()
            if not latest:
                print("No sessions found.")
                continue
            interactive_chat(latest)
            continue

        if cmd == "/help":
            print(
                "/sessions        list sessions\n"
                "/latest          open latest session\n"
                "/open <id>       open session\n"
                "/ask <text>      ask follow-up\n"
                "/follow          follow-up on latest session\n"
                "/clear           clear terminal\n"
                "/help\n"
                "/exit"
            )
            continue

        if cmd == "/clear":
            os.system("clear")
            continue

        if cmd:
            print("Unknown command. Type /help.")


if __name__ == "__main__":
    main()
