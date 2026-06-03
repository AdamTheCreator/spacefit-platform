"""QLoRA supervised fine-tuning: 4-bit frozen base + trainable LoRA adapters.

Reads ``config.yaml``, loads the base model quantized to 4-bit (NF4 + double
quant), attaches LoRA adapters to the attention/MLP projections, and runs
``SFTTrainer`` over the ``messages`` JSONL produced by ``prepare_dataset.py``.
Saves just the adapter (a few MB) to ``adapter_dir``.

Needs a CUDA GPU. See the README for the mental model behind each knob.
"""

from __future__ import annotations

import argparse

import torch
import yaml
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    cfg = load_config(ap.parse_args().config)

    # --- Tokenizer ----------------------------------------------------------
    tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"], use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # --- 4-bit base (frozen) ------------------------------------------------
    # NF4 is a 4-bit datatype tuned for the normal distribution of LLM weights;
    # double-quant quantizes the quant constants too. compute_dtype=bf16 keeps
    # the matmuls in bf16 while the stored weights stay 4-bit.
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
    model.config.use_cache = False  # incompatible with gradient checkpointing
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True
    )

    # --- LoRA adapters (trainable, bf16) ------------------------------------
    lora = LoraConfig(
        r=int(cfg["lora_r"]),
        lora_alpha=int(cfg["lora_alpha"]),
        lora_dropout=float(cfg["lora_dropout"]),
        target_modules=list(cfg["target_modules"]),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()  # sanity: should be <1% of params

    # --- Data: render each conversation to text via the chat template -------
    ds = load_dataset(
        "json",
        data_files={"train": cfg["train_file"], "eval": cfg["eval_file"]},
    )

    def to_text(example: dict) -> dict:
        return {
            "text": tokenizer.apply_chat_template(
                example["messages"], tokenize=False
            )
        }

    ds = ds.map(to_text, remove_columns=ds["train"].column_names)

    # --- Train --------------------------------------------------------------
    sft = SFTConfig(
        output_dir=cfg["output_dir"],
        per_device_train_batch_size=int(cfg["per_device_batch_size"]),
        gradient_accumulation_steps=int(cfg["grad_accum"]),
        learning_rate=float(cfg["learning_rate"]),
        num_train_epochs=int(cfg["epochs"]),
        warmup_ratio=float(cfg.get("warmup_ratio", 0.03)),
        weight_decay=float(cfg.get("weight_decay", 0.0)),
        lr_scheduler_type="cosine",
        logging_steps=int(cfg.get("logging_steps", 5)),
        save_strategy="epoch",
        bf16=True,
        max_seq_length=int(cfg["max_seq_length"]),
        packing=bool(cfg.get("packing", True)),
        dataset_text_field="text",
        report_to="none",
        seed=int(cfg.get("seed", 42)),
    )
    trainer = SFTTrainer(
        model=model,
        args=sft,
        train_dataset=ds["train"],
        eval_dataset=ds["eval"],
        tokenizer=tokenizer,
    )
    trainer.train()

    # --- Save just the adapter ---------------------------------------------
    trainer.model.save_pretrained(cfg["adapter_dir"])
    tokenizer.save_pretrained(cfg["adapter_dir"])
    print(f"\nSaved LoRA adapter → {cfg['adapter_dir']}")


if __name__ == "__main__":
    main()
