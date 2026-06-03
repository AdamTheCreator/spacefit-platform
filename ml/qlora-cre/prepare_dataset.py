"""Build an SFT dataset (OpenAI-style ``messages`` JSONL) for QLoRA.

Two sources:

* ``--source sample`` (default) — validate + copy the bundled CRE examples in
  ``sample_data/`` into ``data/``. No DB, no GPU; lets you run the whole loop now.
* ``--source db`` — read Space Goose's own logs from Postgres (``DATABASE_URL``):
  each ``chat_sessions`` thread becomes a conversation, and successful
  ``tool_call_log`` rows are re-inserted as assistant ``<tool_call>{...}</tool_call>``
  turns so the model learns *your* tool-routing.

Output: ``data/train.jsonl`` + ``data/eval.jsonl``, one ``{"messages": [...]}``
object per line.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

DEFAULT_SYSTEM_PROMPT = (
    "You are Space Goose, an expert commercial real estate analyst. "
    "You can call tools to analyze properties, surface tenant gaps, pull comps, "
    "and search documents. Available tools include void_analysis, "
    "document_search, and listing match. When a tool is needed, emit a single "
    "<tool_call> block with the tool name and JSON arguments."
)


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{i}: invalid JSON ({exc})") from exc
            if not isinstance(obj, dict) or "messages" not in obj:
                raise SystemExit(f"{path}:{i}: each line needs a 'messages' key")
            rows.append(obj)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Source: bundled sample
# --------------------------------------------------------------------------- #
def from_sample(sample_dir: Path, out_dir: Path) -> None:
    train = _read_jsonl(sample_dir / "train.jsonl")
    eval_rows = _read_jsonl(sample_dir / "eval.jsonl")
    _write_jsonl(out_dir / "train.jsonl", train)
    _write_jsonl(out_dir / "eval.jsonl", eval_rows)
    print(f"sample → {len(train)} train / {len(eval_rows)} eval rows in {out_dir}/")


# --------------------------------------------------------------------------- #
# Source: Space Goose Postgres logs
# --------------------------------------------------------------------------- #
def _normalize_dsn(url: str) -> str:
    """Strip the SQLAlchemy ``+driver`` so psycopg accepts the URL."""
    for marker in ("+asyncpg", "+psycopg", "+psycopg2"):
        url = url.replace(marker, "")
    return url


def _tool_call_turn(tool_name: str, arguments_json: str) -> dict:
    """Render a logged tool call as an assistant ``<tool_call>`` turn."""
    try:
        args = json.loads(arguments_json)
    except (json.JSONDecodeError, TypeError):
        args = {"_raw": arguments_json}
    payload = json.dumps({"name": tool_name, "arguments": args}, ensure_ascii=False)
    return {"role": "assistant", "content": f"<tool_call>\n{payload}\n</tool_call>"}


def from_db(out_dir: Path, eval_frac: float, min_turns: int, system_prompt: str) -> None:
    import psycopg  # imported lazily so `--source sample` needs no driver
    from psycopg.rows import dict_row

    dsn = _normalize_dsn(os.environ.get("DATABASE_URL", ""))
    if not dsn:
        raise SystemExit("Set DATABASE_URL to use --source db")

    conversations: list[dict] = []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        sessions = conn.execute(
            "SELECT id FROM chat_sessions ORDER BY created_at"
        ).fetchall()
        for sess in sessions:
            sid = sess["id"]
            msgs = conn.execute(
                "SELECT role, content, created_at FROM chat_messages "
                "WHERE session_id = %s AND visible = true ORDER BY created_at",
                (sid,),
            ).fetchall()
            tools = conn.execute(
                "SELECT tool_name, arguments_json, created_at FROM tool_call_log "
                "WHERE session_id = %s AND status = 'ok' ORDER BY created_at",
                (sid,),
            ).fetchall()

            # Chronological merge of chat turns + tool calls.
            events: list[tuple] = [(m["created_at"], "msg", m) for m in msgs]
            events += [(t["created_at"], "tool", t) for t in tools]
            events.sort(key=lambda e: e[0])

            messages: list[dict] = [{"role": "system", "content": system_prompt}]
            real_turns = 0
            for _, kind, payload in events:
                if kind == "tool":
                    messages.append(
                        _tool_call_turn(payload["tool_name"], payload["arguments_json"])
                    )
                else:
                    role = payload["role"]
                    if role not in ("user", "assistant"):
                        continue
                    content = (payload["content"] or "").strip()
                    if not content:
                        continue
                    messages.append({"role": role, "content": content})
                    real_turns += 1

            if real_turns >= min_turns:
                conversations.append({"messages": messages})

    if not conversations:
        raise SystemExit("No qualifying sessions found (try lowering --min-turns).")

    random.shuffle(conversations)
    n_eval = max(1, int(len(conversations) * eval_frac))
    eval_rows = conversations[:n_eval]
    train_rows = conversations[n_eval:] or conversations[:1]
    _write_jsonl(out_dir / "train.jsonl", train_rows)
    _write_jsonl(out_dir / "eval.jsonl", eval_rows)
    print(f"db → {len(train_rows)} train / {len(eval_rows)} eval conversations")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["sample", "db"], default="sample")
    ap.add_argument("--out-dir", default="data")
    ap.add_argument("--sample-dir", default="sample_data")
    ap.add_argument("--eval-frac", type=float, default=0.1)
    ap.add_argument("--min-turns", type=int, default=2)
    ap.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if args.source == "sample":
        from_sample(Path(args.sample_dir), out_dir)
    else:
        from_db(out_dir, args.eval_frac, args.min_turns, args.system_prompt)


if __name__ == "__main__":
    main()
