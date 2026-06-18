"""Baseten Training job — Qwen2.5-7B-Instruct LoRA fine-tune (Phase 3, bf16).

Launch:   cd backend/finetune/training && truss train push config.py
Logs:     truss train logs --job-id <id> --tail
Deploy:   truss train deploy_checkpoints --job-id <id>   (-> LoRA adapter on the L4)

The job runs run.sh, which runs Axolotl against qwen_lora.yaml using the
data/ dir uploaded alongside this config. One A100 is ample for a 7B LoRA on
~29 examples (D21: venue = Baseten Training; cost ~a few $ for this run).
"""

from truss_train import definitions
from truss.base import truss_config

training_job = definitions.TrainingJob(
    # Axolotl preinstalled image keeps run.sh to a single `axolotl train`.
    image=definitions.Image(base_image="axolotlai/axolotl:main-latest"),
    compute=definitions.Compute(
        node_count=1,
        accelerator=truss_config.AcceleratorSpec(
            accelerator=truss_config.Accelerator.A100,
            count=1,
        ),
    ),
    runtime=definitions.Runtime(
        start_commands=["/bin/sh -c 'chmod +x ./run.sh && ./run.sh'"],
        cache_config=definitions.CacheConfig(enabled=True),
        checkpointing_config=definitions.CheckpointingConfig(enabled=True),
    ),
)

training_project = definitions.TrainingProject(
    name="spacegoose-advisor-lora",
    job=training_job,
)
