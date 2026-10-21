"""Small laptop commands used by the lab Make targets."""

import argparse
import json
import os
import sys
from datetime import date

from anthropic import AnthropicBedrockMantle

from app.ai.agenda import parse_agenda
from app.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["hello", "parse"])
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "hello":
        msg = AnthropicBedrockMantle(aws_region=settings.parser_region).messages.create(
            model=settings.parser_model,
            max_tokens=1024,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "In one sentence: what is an ISO week?"}],
        )
        print(next(block.text for block in msg.content if block.type == "text"))
        print(
            json.dumps(
                {
                    "stop_reason": msg.stop_reason,
                    "input_tokens": msg.usage.input_tokens,
                    "output_tokens": msg.usage.output_tokens,
                }
            )
        )
        return 0
    agenda, usage = parse_agenda(
        os.environ.get("TEXT", ""),
        date.fromisoformat(os.environ.get("TODAY", date.today().isoformat())),
        os.environ.get("TZ", "Europe/Kyiv"),
    )
    print(
        json.dumps({"agenda": agenda.model_dump(mode="json"), "usage": usage}, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
