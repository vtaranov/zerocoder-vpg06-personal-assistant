"""CLI uses the same service as Telegram."""
import argparse
import json
from assistant import Assistant

def main():
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--owner", default="cli:demo")
    args = p.parse_args()
    result = Assistant().handle(args.owner, args.text)
    print(json.dumps({"answer": result["answer"], "calls": result["calls"],
                      "photos": len(result["attachments"])}, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()
