"""Merge the LoRA adapter into the base and (optionally) push to the HF Hub.

HF Inference Endpoints serve a single set of weights, so we fold the adapter
back into the base (``merge_and_unload``) and save/push the merged model. Loaded
in bf16 (not 4-bit) so the merge is clean — this needs ~14GB of RAM/VRAM for a
7B; CPU is fine if you have the RAM.

    python merge_and_push.py --adapter outputs/qlora-cre/adapter \
        --repo your-username/spacegoose-cre-qwen7b      # omit --repo to merge locally
"""

from __future__ import annotations

import argparse

import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", default="merged")
    ap.add_argument("--repo", default="", help="HF repo id to push to (optional)")
    args = ap.parse_args()
    cfg = load_config(args.config)

    tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"], use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"],
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    )
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()

    merged.save_pretrained(args.out, safe_serialization=True)
    tokenizer.save_pretrained(args.out)
    print(f"Merged model → {args.out}/")

    if args.repo:
        # Requires `huggingface-cli login` or HF_TOKEN in the environment.
        merged.push_to_hub(args.repo)
        tokenizer.push_to_hub(args.repo)
        print(f"Pushed → https://huggingface.co/{args.repo}")
        print(
            "Deploy it on HF Inference Endpoints, then point Space Goose's "
            "openai_compatible base_url at <endpoint>/v1 (see README)."
        )


if __name__ == "__main__":
    main()
