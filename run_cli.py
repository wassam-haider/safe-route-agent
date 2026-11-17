import logging

from app.agent import run_turn

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    print("SafeRoute CLI. Type 'exit' to quit.")
    while True:
        text = input("\nYou: ").strip()
        if text.lower() in {"exit", "quit"}:
            break
        if not text:
            continue
        reply = run_turn("cli", text)
        print("\nAgent:", reply["message"])


if __name__ == "__main__":
    main()