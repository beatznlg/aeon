#!/usr/bin/env python3
# ============================================================
#  AEON Chat CLI — thin entrypoint for the Next.js chat API.
#  Reads AEON_LLM_PROVIDER and provider keys from env.
#  Usage: python aeon_chat.py "<user query>" [--system "<system prompt>"]
# ============================================================
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="AEON chat CLI")
    parser.add_argument("query", help="User query text")
    parser.add_argument("--system", default=None, help="Optional system prompt")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max new tokens")
    args = parser.parse_args()

    # Import here so the heavy aeon deps are only loaded when needed.
    from aeon import ReflectiveAgent

    agent = ReflectiveAgent()
    result = agent.act(args.query)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
