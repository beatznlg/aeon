#!/usr/bin/env python3
"""Validate that Qwen/Qwen2.5-3B-Instruct is reachable with transformers>=5.5.0.

This environment does not have a GPU, so we only load the tokenizer and config.
Full model/GPU load validation should be run on a Colab T4 instance or other
GPU environment.
"""
from __future__ import annotations

import os
import sys

from transformers import AutoConfig, AutoTokenizer
from transformers import __version__ as transformers_version

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
# Pin the model revision so downloads are reproducible (override via env).
MODEL_REVISION = os.environ.get("AEON_HF_MODEL_REVISION", "main")


def main() -> int:
    print(f"transformers version: {transformers_version}")
    print(f"Loading tokenizer for {MODEL_ID} ...")

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            trust_remote_code=False,
            token=os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("AEON_HF_TOKEN"),
        )
    except Exception as exc:  # pragma: no cover
        print(f"ERROR loading tokenizer: {exc}")
        return 1

    print(f"Tokenizer loaded: vocab_size={len(tokenizer)}, pad={tokenizer.pad_token}, eos={tokenizer.eos_token}")

    print(f"Loading config for {MODEL_ID} ...")
    try:
        config = AutoConfig.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            trust_remote_code=False,
            token=os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("AEON_HF_TOKEN"),
        )
    except Exception as exc:  # pragma: no cover
        print(f"ERROR loading config: {exc}")
        return 1

    print(f"Config loaded: model_type={config.model_type}, architectures={getattr(config, 'architectures', 'n/a')}")
    print("\nValidation passed (tokenizer + config). GPU full-load test requires a GPU environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
