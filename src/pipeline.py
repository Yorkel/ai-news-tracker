"""
pipeline.py
Runs the pipeline in one of three modes.

  python src/pipeline.py --training
    Build training data + train model:
    provide train/val CSVs -> embed -> train -> evaluate

  python src/pipeline.py --inference
    Weekly inference from Supabase:
    pull from Supabase → classify (via deployed classifier API) → monitor

  python src/pipeline.py --classify-only
    Classify existing local data (skip Supabase pull):
    classify (via deployed classifier API) → monitor

Run from the project root.
"""

import argparse
import importlib
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src.*` imports resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Training: start from data/modelling/train.csv and val.csv.
STEPS_TRAINING = [
    ("s04_embed",      "src.classify.s04_embed"),
    ("s05_train",      "src.classify.s05_train"),
    ("s06_evaluate",   "src.classify.s06_evaluate"),
]

# Weekly inference: pull from Supabase + classify (via deployed API) + score + push back.
# Drift (s09_monitor) and fairness (fairness_audit) are NOT in this list — they run as
# separate GitHub Actions workflows (drift.yml / fairness.yml) triggered after classify.yml
# completes, so the inference pipeline stays focused on producing predictions.
STEPS_INFERENCE = [
    ("s07_pull",        "src.inference.s07_pull_supabase"),
    ("classify_via_api","src.inference.classify_via_api"),
    ("scoring",         "src.inference.scoring"),
    ("s10_push",        "src.inference.s10_push_supabase"),
]

# Classify only: run on existing local data (skip Supabase pull)
STEPS_CLASSIFY_ONLY = [
    ("classify_via_api","src.inference.classify_via_api"),
    ("scoring",         "src.inference.scoring"),
]


def run_step(name: str, module_path: str):
    print(f"\n{'='*50}")
    print(f"Running {name}...")
    print(f"{'='*50}")
    module = importlib.import_module(module_path)
    module.main()


def main():
    parser = argparse.ArgumentParser(description="News Tracker Classification Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--training",
        action="store_true",
        help="Embed supplied train/val CSVs, train the model, and evaluate.",
    )
    group.add_argument(
        "--inference",
        action="store_true",
        help="Pull from Supabase + classify + monitor (weekly workflow).",
    )
    group.add_argument(
        "--classify-only",
        action="store_true",
        help="Classify existing local data + monitor (skip Supabase pull).",
    )
    # Optional date window for --inference. Steps read these from env so we
    # don't have to thread args through every module's main() signature.
    parser.add_argument(
        "--since",
        help="Inference only: include articles with article_date >= YYYY-MM-DD",
    )
    parser.add_argument(
        "--until",
        help="Inference only: include articles with article_date <= YYYY-MM-DD",
    )
    args = parser.parse_args()

    if args.training:
        steps = STEPS_TRAINING
    elif args.inference:
        steps = STEPS_INFERENCE
        if args.since:
            os.environ["INFERENCE_SINCE"] = args.since
        if args.until:
            os.environ["INFERENCE_UNTIL"] = args.until
    else:
        steps = STEPS_CLASSIFY_ONLY

    for name, module_path in steps:
        run_step(name, module_path)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
