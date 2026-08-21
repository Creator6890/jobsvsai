"""Run the Phase 5B candidate calculation over the coverage-completed namespace.

Phase 5B is Phase 5 with more evidence and nothing else. It reuses the validated engine
verbatim — capability taxonomy, mapping rubric, commercially_deployable Frontier index,
Task Capability Fit, Automation Feasibility, task-level Augmentation Potential, the Phase
4D direct structural proxies, the JVS 2.0 replacement-risk factor definitions, the
confidence methodology, the provisional adoption and labour-market inputs, and archetype
scoring left disabled. Only `phase5_task_mapping_scope` differs, because
`generate_phase5b_coverage_completion` mapped the tasks Phase 5's 70% stopping rule skipped.

This is an isolated candidate run. It does not touch the Phase 5 run it is compared
against, does not write production scores, does not activate any occupation, and does not
change which scoring model is active.

  # score
  docker compose run --rm worker python -m scoring.run_phase5b_coverage_completion \
      --run-version phase5b-coverage-completion-2026q3-v1 --run-kind bounded_corpus

  # deterministic replay of that run
  docker compose run --rm worker python -m scoring.run_phase5b_coverage_completion \
      --run-version phase5b-coverage-completion-2026q3-replay-v1 \
      --run-kind deterministic_replay \
      --previous-run-version phase5b-coverage-completion-2026q3-v1
"""

from __future__ import annotations

import argparse
import asyncio
import json

try:
    from .run_phase5_bounded import run
except ImportError:
    from run_phase5_bounded import run


NAMESPACE_VERSION = "phase5b-candidate-2026q3-v1"
MAPPING_RUN_VERSION = "phase5b-completion-mapper-v1-2026q3"
MAPPING_SCOPE_VERSION = "phase5b-mapping-completion-v1"
RUN_VERSION = "phase5b-coverage-completion-2026q3-v1"
REPLAY_VERSION = "phase5b-coverage-completion-2026q3-replay-v1"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-version", default=RUN_VERSION)
    parser.add_argument("--run-kind", choices=["bounded_corpus", "deterministic_replay"],
                        default="bounded_corpus")
    parser.add_argument("--previous-run-version")
    parser.add_argument("--namespace-version", default=NAMESPACE_VERSION)
    parser.add_argument("--mapping-run-version", default=MAPPING_RUN_VERSION)
    parser.add_argument("--mapping-scope-version", default=MAPPING_SCOPE_VERSION)
    args = parser.parse_args()
    print(json.dumps(await run(
        args.run_version,
        args.run_kind,
        args.previous_run_version,
        args.namespace_version,
        args.mapping_run_version,
        args.mapping_scope_version,
    ), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
