#!/bin/sh
# Baseten Training entrypoint: run the Axolotl LoRA fine-tune, then copy the
# adapter into Baseten's checkpoint dir so it's retrievable / deployable.
set -eu

echo "==> Qwen2.5-7B LoRA fine-tune (Axolotl)"
axolotl train qwen_lora.yaml

OUT="${BT_CHECKPOINT_DIR:-}"
if [ -n "$OUT" ]; then
  echo "==> copying adapter to checkpoint dir: $OUT"
  mkdir -p "$OUT"
  cp -r ./lora-out/* "$OUT"/
fi
echo "==> done"
