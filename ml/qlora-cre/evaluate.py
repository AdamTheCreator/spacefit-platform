"""Evaluate the adapter — with a TOOL-CALLING REGRESSION SLICE.

For each held-out conversation we feed everything up to the final assistant turn
and generate it. If the gold turn is a ``<tool_call>``, we score whether the
model emitted the *same tool name* with *parseable JSON arguments* — that's the
regression slice that catches catastrophic forgetting of function-calling.

Run it twice and compare:

    python evaluate.py --adapter outputs/qlora-cre/adapter   # fine-tuned
    python evaluate.py --adapter ""                          # base, no adapter

Only ship the adapter if tool-call accuracy did NOT drop vs the base.
"""

from __future__ import annotations

import argparse
import json
import re

import torch
import yaml
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

_TOOL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def extract_tool_call(text: str) -> dict | None:
    """Return the first ``<tool_call>`` JSON object, or None."""
    m = _TOOL_RE.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {"_unparseable": True}
    return obj if isinstance(obj, dict) else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument(
        "--adapter",
        default="",
        help="Path to the LoRA adapter; empty string = evaluate the base model.",
    )
    ap.add_argument("--max-new-tokens", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0, help="0 = all eval rows")
    args = ap.parse_args()
    cfg = load_config(args.config)

    tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"], use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"],
        quantization_config=bnb,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
        label = f"adapter={args.adapter}"
    else:
        label = "base model (no adapter)"
    model.eval()

    rows = []
    with open(cfg["eval_file"], encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if args.limit:
        rows = rows[: args.limit]

    tool_total = tool_name_ok = tool_json_ok = 0
    text_total = text_nonempty = 0

    for ex in rows:
        messages = ex["messages"]
        if len(messages) < 2 or messages[-1]["role"] != "assistant":
            continue
        prompt_msgs, gold = messages[:-1], messages[-1]
        prompt = tokenizer.apply_chat_template(
            prompt_msgs, add_generation_prompt=True, tokenize=False
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        gen = tokenizer.decode(
            out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )

        gold_call = extract_tool_call(gold["content"])
        if gold_call is not None:
            tool_total += 1
            pred_call = extract_tool_call(gen)
            if pred_call and not pred_call.get("_unparseable"):
                tool_json_ok += 1
                if pred_call.get("name") == gold_call.get("name"):
                    tool_name_ok += 1
        else:
            text_total += 1
            if gen.strip():
                text_nonempty += 1

    print(f"\n=== Eval: {label} ===")
    print(f"rows evaluated: {len(rows)}")
    if tool_total:
        print(
            f"tool-call name accuracy : {tool_name_ok}/{tool_total} "
            f"({tool_name_ok / tool_total:.0%})"
        )
        print(
            f"tool-call JSON validity : {tool_json_ok}/{tool_total} "
            f"({tool_json_ok / tool_total:.0%})"
        )
    if text_total:
        print(
            f"text responses non-empty: {text_nonempty}/{text_total} "
            f"({text_nonempty / text_total:.0%})"
        )
    print("\nCompare these numbers to the base run before shipping the adapter.")


if __name__ == "__main__":
    main()
