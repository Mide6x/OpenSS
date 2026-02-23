import os

from bson import ObjectId
from openai import OpenAI
from dotenv import load_dotenv

from config import load_config
from db import add_message, get_session_messages, list_sessions


load_dotenv()
CONFIG = load_config()
MODEL = os.getenv("SS_MODEL", CONFIG["model"])
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

current_session = None


def ask_llm(context: str, question: str) -> str:
    prompt = CONFIG["prompt_followup"].format(context=context, question=question)
    r = client.responses.create(model=MODEL, input=prompt)
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
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    
    console = Console()
    current_session = session_id
    
    console.print("\n[bold green]Chat session active.[/bold green] [dim](Press Enter on empty line to exit)[/dim]\n")
    
    while True:
        try:
            q = Prompt.ask("[bold blue]Ask[/bold blue]")
        except EOFError:
            break
        if not q:
            break
            
        with console.status("[dim]Thinking...[/dim]"):
            ctx = load_context(current_session)
            ans = ask_llm(ctx, q)
            
        console.print(Markdown(ans))
        
        # Explicit Code Display for follow-ups
        from ss_ai import extract_first_code_block, copy_to_clipboard
        from config import load_config
        cfg = load_config()
        
        code_block = extract_first_code_block(ans)
        if code_block:
            console.print(Panel(code_block, title="Extracted Code", border_style="bold yellow"))
            
        # Autocopy for follow-ups
        if cfg.get("autocopy", False):
            mode = cfg.get("autocopy_mode", "answer")
            payload = code_block if (mode == "code" and code_block) else ans
            if payload:
                copy_to_clipboard(payload)
                msg = "Code copied" if mode == "code" and code_block else "Answer copied"
                console.print(f"[dim italic]({msg} to clipboard)[/dim italic]")

        console.print("") # Padding
        add_message(current_session, "user", q)
        add_message(current_session, "assistant", ans)


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
