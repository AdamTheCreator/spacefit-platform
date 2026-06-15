# Qwen2.5-7B-Instruct on Baseten (L4)

The candidate model (D10) served on our target hardware via a **config-only Truss**
wrapping vLLM's OpenAI-compatible server. This is the controlled serving stack that
fixes the HF-router flakiness (§4.3 in `MIGRATION.md`): one known tool-call parser,
our own concurrency limits, our own GPU.

## Deploy

```bash
cd backend
export BASETEN_API_KEY=...        # never commit this
truss push baseten/qwen25-7b-instruct      # development deployment (scale-to-zero)
```

`truss push` builds the container on Baseten and boots vLLM, which downloads the
(public) Qwen weights on first start. Watch the build in the Baseten dashboard or
poll the Management API until the deployment is `ACTIVE`.

## Enable scale-to-zero (post-deploy, via API)

Autoscaling is **not** in `config.yaml` — it's set on the deployment. `min_replica`
defaults to `0` (already scale-to-zero), but set it explicitly and tune the sleep delay:

```bash
curl -X PATCH \
  https://api.baseten.co/v1/models/{model_id}/deployments/{deployment_id}/autoscaling_settings \
  -H "Authorization: Api-Key $BASETEN_API_KEY" \
  -d '{"min_replica": 0, "max_replica": 1, "scale_down_delay": 300}'
```

`min_replica: 0` → the L4 sleeps after `scale_down_delay` seconds of no traffic
(cheap when idle). For a demo/onboarding window, PATCH `min_replica: 1` to keep it
warm (the "always-on toggle" from decision D6), then back to 0 afterward.

## Benchmark it (both eval dimensions)

Point the eval harness at the deployment's OpenAI-compatible endpoint:

```bash
cd backend
EVAL_PROVIDER=openai_compatible EVAL_MODEL=Qwen/Qwen2.5-7B-Instruct \
  EVAL_API_KEY=$BASETEN_API_KEY \
  EVAL_BASE_URL=https://model-{model_id}.api.baseten.co/environments/production/sync/v1 \
  python -m evals.run_eval --label qwen25-7b-baseten      # tool-calling

# advisory dimension (judge stays on Anthropic)
EVAL_PROVIDER=openai_compatible EVAL_MODEL=Qwen/Qwen2.5-7B-Instruct \
  EVAL_API_KEY=$BASETEN_API_KEY EVAL_BASE_URL=... \
  JUDGE_PROVIDER=anthropic JUDGE_MODEL=claude-sonnet-4-6 JUDGE_API_KEY=sk-ant-... \
  python -m evals.run_advisory --label qwen25-7b-baseten
```

## Deliberate choices + planned optimizations

- **bf16, not quantized (yet).** First we measure the model's *true* quality vs. the
  Haiku baseline. Then we test `--quantization fp8` (L4 supports FP8) to free VRAM /
  raise throughput, and re-run the evals to see whether quality holds. Quant-vs-quality
  is its own experiment, not an assumption.
- **No weight cache (yet).** vLLM downloads weights on cold start, so the first wake is
  slow. Once we've measured that cold start (a Phase-4 goal), we add Baseten's weight
  caching / `model_cache` to shrink it — the scale-to-zero ↔ cold-start tradeoff from D6.
- **`max_model_len 16384`** is sized for the eval + headroom on a 24 GB L4; raise it
  only with measured KV-cache room (or after FP8).
