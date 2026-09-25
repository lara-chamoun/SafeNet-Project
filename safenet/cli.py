import argparse
import json
import uuid

from dotenv import load_dotenv

from .graph import build_graph
from .models import CyberSafetyState


DEMOS = {
    "low": "I received the password reset email I requested and completed it inside the official app.",
    "medium": "Urgent: my bank account will be suspended. The message tells me to verify at http://bank-check.example but I did not click it.",
    "high": "I clicked a bank link, entered my password and verification code, and then saw a login I don't recognize.",
}


def run_case(message: str, live: bool, thread_id: str) -> CyberSafetyState:
    graph = build_graph()
    initial = CyberSafetyState(user_message=message, use_live_llm=live)
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\nINPUT: {message}\n")
    final_values = None
    for update in graph.stream(initial, config=config, stream_mode="updates"):
        node, partial = next(iter(update.items()))
        printable = {
            k: (v.model_dump() if hasattr(v, "model_dump") else v)
            for k, v in partial.items()
            if k in {"current_stage", "risk_score", "risk_level", "route_taken", "parsed_domains", "iteration"}
        }
        print(f"[{node}] partial update: {json.dumps(printable, indent=2)}")

    snapshot = graph.get_state(config)
    final_values = snapshot.values
    final = CyberSafetyState.model_validate(final_values)
    print("\n" + final.final_report)
    print(f"\nExecution path: {' -> '.join(final.agents_completed)}")
    return final


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="SafeNet AI cybersecurity assistant")
    parser.add_argument("--message", help="Describe the suspicious event")
    parser.add_argument("--demo", choices=["low", "medium", "high", "all"])
    parser.add_argument("--live", action="store_true", help="Use OpenAI Structured Output Mode")
    parser.add_argument("--thread-id", default=None, help="MemorySaver conversation ID")
    args = parser.parse_args()

    if not args.message and not args.demo:
        parser.error("Provide --message or --demo.")

    cases = DEMOS if args.demo == "all" else ({args.demo: DEMOS[args.demo]} if args.demo else {"custom": args.message})
    base_thread = args.thread_id or str(uuid.uuid4())
    for name, message in cases.items():
        print(f"\n{'=' * 18} {name.upper()} CASE {'=' * 18}")
        run_case(message, args.live, f"{base_thread}-{name}")


if __name__ == "__main__":
    main()
