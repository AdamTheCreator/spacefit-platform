"""Submit the advisory LoRA fine-tune to Together AI (D21 pivot).

Baseten Training wasn't available on the account, so we train on Together and
still SERVE the adapter on the Baseten L4 (train-venue != serve-venue, by design).
Same dataset (chat JSONL — already Together's format) and hyperparameters.

    cd backend
    export TOGETHER_API_KEY=...
    python -m finetune.together_submit list-models      # confirm the Qwen base string
    python -m finetune.together_submit submit            # upload + launch LoRA job -> JOB ID
    python -m finetune.together_submit status --job-id ft-...
    python -m finetune.together_submit download --job-id ft-...   # pull the adapter for the L4
"""

from __future__ import annotations

import argparse
import os
import time

DEFAULT_TRAIN = "finetune/dataset/memos/train.jsonl"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"  # confirm via list-models


def _client():
    from together import Together

    key = os.environ.get("TOGETHER_API_KEY")
    if not key:
        raise SystemExit("set TOGETHER_API_KEY")
    return Together(api_key=key)


def list_models(args) -> None:
    """Print fine-tunable Qwen base models so we use Together's exact string."""
    c = _client()
    for m in c.models.list():
        name = getattr(m, "id", None) or getattr(m, "name", None)
        ft = getattr(m, "fine_tuning", None)
        if name and "qwen" in str(name).lower():
            print(name, f"(fine_tuning={ft})" if ft is not None else "")


def submit(args) -> None:
    c = _client()
    print(f"uploading {args.train} …")
    f = c.files.upload(file=args.train, purpose="fine-tune", check=True)
    print("file id:", f.id)
    while True:
        meta = c.files.retrieve(f.id)
        st = getattr(meta, "processing_status", None)
        if st == "COMPLETED":
            break
        if st in ("FAILED", "ERROR"):
            raise SystemExit(f"file processing failed: {st}")
        print("  file status:", st)
        time.sleep(5)
    print("creating LoRA job …")
    # v1 lesson: omitting lora_r/lora_alpha gets Together's defaults (r=64,
    # alpha=128) — 4x our intended capacity, which overfit 29 examples badly
    # (off-format repetition loops). Always pin the rank explicitly.
    job = c.fine_tuning.create(
        training_file=f.id,
        model=args.model,
        n_epochs=args.epochs,
        n_checkpoints=1,
        learning_rate=args.lr,
        warmup_ratio=0.0,
        train_on_inputs="auto",   # learn only the advisory outputs, mask inputs
        lora=True,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        suffix=args.suffix,
    )
    print("JOB ID:", job.id)
    print("monitor:  python -m finetune.together_submit status --job-id", job.id)


def status(args) -> None:
    c = _client()
    s = c.fine_tuning.retrieve(id=args.job_id)
    print("status:", getattr(s, "status", None))
    print("output model:", getattr(s, "x_model_output_name", None) or getattr(s, "output_name", None))


def download(args) -> None:
    # SDK >= 2.x: fine_tuning.content() (the old .download() is gone). Returns
    # a zstd-compressed tar of the PEFT adapter dir; extract with zstandard+tarfile.
    c = _client()
    out = args.out or f"{args.job_id}_adapter.tar.zst"
    resp = c.fine_tuning.content(ft_id=args.job_id, checkpoint="adapter")
    resp.write_to_file(out)
    print("downloaded adapter archive ->", out)
    print("extract: python -c \"import zstandard,tarfile,io; "
          "tarfile.open(fileobj=io.BytesIO(zstandard.ZstdDecompressor()"
          f".stream_reader(open('{out}','rb')).read())).extractall('adapter')\"")


def main() -> int:
    ap = argparse.ArgumentParser(description="Together AI LoRA fine-tune for the advisory model.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-models").set_defaults(func=list_models)

    s = sub.add_parser("submit")
    s.add_argument("--train", default=DEFAULT_TRAIN)
    s.add_argument("--model", default=DEFAULT_MODEL)
    s.add_argument("--epochs", type=int, default=4)
    s.add_argument("--lr", type=float, default=1e-4)
    s.add_argument("--lora-r", type=int, default=16, help="LoRA rank (matches qwen_lora.yaml)")
    s.add_argument("--lora-alpha", type=int, default=32)
    s.add_argument("--suffix", default="spacegoose-advisor")
    s.set_defaults(func=submit)

    st = sub.add_parser("status")
    st.add_argument("--job-id", required=True)
    st.set_defaults(func=status)

    d = sub.add_parser("download")
    d.add_argument("--job-id", required=True)
    d.add_argument("--out", default="")
    d.set_defaults(func=download)

    args = ap.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
