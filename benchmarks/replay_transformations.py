"""Replay cached transformations through the semantic evaluator only.

Offline mode is the default and never constructs a provider or makes a network
call. Live mode requires both ``--live`` and the existing
``RUN_SEMANTIC_BENCHMARKS=1`` authorization gate.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from task_decomposition.contracts.stages import TransformationDecompositionResult
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    TransformationSemanticCriterion,
    TransformationSemanticEvaluationRequest,
)
from task_decomposition.evaluation.rubric import (
    TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
)

ARTIFACTS = {
    "invoice_review": Path("notebooks/outputs/17385639a3fe.json"),
    "production_scheduling": Path("notebooks/outputs/02b301201630.json"),
    "claims_triage": Path("notebooks/outputs/03a8122d6151.json"),
    "saas_customer_support": Path("notebooks/outputs/cde43a77da88.json"),
}

EXPECTED_BEHAVIOR = {
    "invoice_review": {
        "criteria": (
            TransformationSemanticCriterion.HUMAN_RESPONSIBILITY_COMPLETENESS,
        ),
        "description": "consider omitted human invoice authorization effort",
    },
    "production_scheduling": {
        "criteria": (
            TransformationSemanticCriterion.HUMAN_RESPONSIBILITY_COMPLETENESS,
        ),
        "description": "distinguish management decision effort from communication effort",
    },
    "claims_triage": {
        "criteria": (TransformationSemanticCriterion.OCCURRENCE_ASSUMPTIONS,),
        "description": "assess combined exception/uncertainty triggers without rejecting a reasonable planning assumption solely for lacking measurement",
    },
    "saas_customer_support": {
        "criteria": (
            TransformationSemanticCriterion.HUMAN_RESPONSIBILITY_COMPLETENESS,
        ),
        "description": "assess customer-response ownership without equating accountability with manual sending",
    },
}


def load_cached_transformation(
    case_key: str,
) -> tuple[dict[str, Any], TransformationDecompositionResult]:
    """Load and validate one cached transformation without provider execution."""

    path = ARTIFACTS[case_key]
    artifact = json.loads(path.read_text(encoding="utf-8"))
    result = TransformationDecompositionResult.model_validate(artifact["result"])
    return artifact, result


def build_evaluation_request(
    case_key: str,
) -> TransformationSemanticEvaluationRequest:
    """Build the evaluator request from the frozen cached result only."""

    _, result = load_cached_transformation(case_key)

    task = result.task_decomposition.operational_decomposition.task
    request = TransformationSemanticEvaluationRequest(
        task=task,
        # Cached transformations predate this request field. Keep the
        # evaluator contract satisfied without inferring context from prose.
        transformation_context={},
        parent_output_contract=result.task_decomposition.parent_output_contract,
        task_decomposition=result.task_decomposition,
        retain_remove_classification=result.retain_remove_classification,
        agentic_task_synthesis=result.agentic_task_synthesis,
        human_agent_activity_modeling=result.human_agent_activity_modeling,
        activity_effort_estimation=result.activity_effort_estimation,
        accounting=result.accounting,
        rubric_version=TRANSFORMATION_SEMANTIC_EVALUATION_RUBRIC_VERSION,
    )
    return request


def offline_case(case_key: str) -> dict[str, Any]:
    """Validate and summarize one replay request without invoking an evaluator."""

    request = build_evaluation_request(case_key)
    payload = {
        "task": request.task.model_dump(mode="json"),
        "transformation_context": request.transformation_context,
        "parent_output_contract": (
            request.parent_output_contract.model_dump(mode="json")
            if request.parent_output_contract
            else None
        ),
        "task_decomposition": request.task_decomposition.model_dump(mode="json"),
        "retain_remove_classification": request.retain_remove_classification.model_dump(
            mode="json"
        ),
        "agentic_task_synthesis": request.agentic_task_synthesis.model_dump(
            mode="json"
        ),
        "human_agent_activity_modeling": request.human_agent_activity_modeling.model_dump(
            mode="json"
        ),
        "activity_effort_estimation": request.activity_effort_estimation.model_dump(
            mode="json"
        ),
        "accounting": request.accounting.model_dump(mode="json"),
        "rubric_version": request.rubric_version,
    }
    return {
        "case_key": case_key,
        "status": "validated",
        "task_name": request.task.task_name,
        "w0": str(request.accounting.w0),
        "w1": str(request.accounting.w1),
        "subtask_count": len(
            request.task_decomposition.operational_decomposition.operational_subtasks
        ),
        "agentic_task_count": len(request.agentic_task_synthesis.agentic_tasks),
        "human_activity_count": len(request.human_agent_activity_modeling.activities),
        "effort_estimate_count": len(
            request.activity_effort_estimation.activity_effort_estimates
        ),
        "payload_keys": sorted(payload),
        "expected_behavior": EXPECTED_BEHAVIOR[case_key]["description"],
        "semantic_decision": None,
        "findings": [],
        "evaluator": None,
        "token_usage": None,
        "cost": None,
    }


def _finding_payload(finding) -> dict[str, Any]:
    return {
        "criterion": finding.criterion.value if finding.criterion else None,
        "severity": finding.severity.value,
        "message": finding.message,
        "evidence": finding.evidence,
        "affected_references": list(finding.affected_references),
        "subtask_id": finding.subtask_id,
    }


def live_case(case_key: str, provider) -> dict[str, Any]:
    """Invoke only ``provider.evaluate`` for one validated cached transformation."""

    request = build_evaluation_request(case_key)
    result = provider.evaluate(request)
    evaluation = SemanticEvaluation.model_validate(result)
    provenance = evaluation.evaluator_provenance
    return {
        "case_key": case_key,
        "status": "evaluated",
        "w0": str(request.accounting.w0),
        "w1": str(request.accounting.w1),
        "semantic_decision": evaluation.decision.value,
        "findings": [_finding_payload(finding) for finding in evaluation.findings],
        "evaluator": (
            {
                "provider": provenance.provider_id,
                "model": provenance.model_id,
            }
            if provenance
            else None
        ),
        "token_usage": None,
        "cost": None,
        "expected_behavior": EXPECTED_BEHAVIOR[case_key]["description"],
    }


def _provider(name: str):
    # Reuse the existing benchmark provider map and its provider configuration.
    from run_live import _provider_specs

    specs = _provider_specs()
    if name not in specs:
        raise ValueError(f"unknown provider: {name}")
    key, factory = specs[name]
    if not os.getenv(key):
        raise RuntimeError(f"live replay requires configured {key}")
    return factory()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--case", choices=tuple(ARTIFACTS), action="append")
    args = parser.parse_args()
    cases = args.case or list(ARTIFACTS)

    if not args.live:
        for case_key in cases:
            print(json.dumps(offline_case(case_key), sort_keys=True))
        return 0

    if os.getenv("RUN_SEMANTIC_BENCHMARKS") != "1":
        print("Live replay skipped: set RUN_SEMANTIC_BENCHMARKS=1 to enable.")
        return 0
    provider = _provider(args.provider)
    for case_key in cases:
        print(json.dumps(live_case(case_key, provider), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
