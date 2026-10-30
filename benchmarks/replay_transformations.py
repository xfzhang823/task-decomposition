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

TASK_CASES = {
    "invoice_review": {
        "label": "Supplier invoice review",
        "task_name": "Review and approve a supplier invoice",
        "task_description": "You work in accounts payable at a mid-sized manufacturing company. A supplier has sent an invoice for raw materials delivered to your factory. It lists the supplier's details, purchase order number, items, quantities, prices, taxes, and payment terms. Your task is to check that the invoice is genuine, the numbers are right, and everything matches what the company ordered and received. You might run into things like a wrong price, a missing purchase order, quantities that don't match, a duplicate invoice, or charges you don't recognize. If something doesn't add up, you'll need to check with purchasing, the warehouse, or the supplier. Once everything checks out and any issues are sorted out, approve the invoice for payment under company policy.",
        "domain": "accounts_payable",
        "operating_model": "A human AP approver must approve the invoice before payment; AI may perform checks but is not the final approver.",
    },
    "saas_customer_support": {
        "label": "SaaS customer support",
        "task_name": "Triage a software customer support ticket",
        "task_description": "You work in customer support at a B2B software company. A customer reports that several employees can't access their reporting dashboard after a recent software update. They've included a short description, screenshots, and roughly when the problem started. You can look up their account information, previous support tickets, product documentation, and known incidents. Your job is to figure out what kind of issue this is, how serious it might be, and how it's affecting the customer's business. Some tickets are straightforward, while others may involve widespread outages, unclear symptoms, or problems that need specialist attention. Decide who should handle the issue, make sure the ticket gets to the right team with the relevant information, and let the customer know what happens next. You're responsible for triaging the ticket, not troubleshooting or resolving the underlying problem.",
        "domain": "customer_support",
        "operating_model": "A support agent owns the customer response; technical escalation remains outside this parent-task boundary.",
    },
    "production_scheduling": {
        "label": "Manufacturing production scheduling",
        "task_name": "Prepare a weekly production schedule",
        "task_description": "You're a production planner at a packaged food factory, and you need to put together next week's schedule for several packaging lines. You have customer orders, demand forecasts, inventory levels, equipment availability, staff schedules, and planned maintenance times to work with. Products take different amounts of time to run and need different packaging setups. Switching products can also mean stopping to clean and reset the equipment. Your task is to build a schedule the factory can actually deliver, taking into account deadlines, line capacity, available materials, staffing, and production priorities. If there isn't enough capacity or some materials won't be available, work through the options with production management before sending the schedule to the factory floor.",
        "domain": "operations",
        "operating_model": "A production planner or manager reviews the schedule before it is released to the factory floor.",
    },
    "claims_triage": {
        "label": "Auto insurance claims triage",
        "task_name": "Triage a personal auto collision claim",
        "task_description": "You handle new auto insurance claims. A policyholder reports a two-car collision at an intersection and sends in their account of what happened, vehicle details, damage photos, the other driver's contact and insurance information, and a police report number. Some details might be missing or conflicting, and there may not be a repair estimate yet. Your task is to check the claim against the policy and available records, see whether there's enough information to move it forward, flag missing documents or possible coverage issues, and send it to the right claims team. Straightforward claims can go through the usual process. Claims involving injuries, conflicting accounts, signs of possible fraud, or complicated coverage questions need specialist attention. You're getting the claim ready for an adjuster, who will make the final coverage and liability decisions.",
        "domain": "insurance",
        "operating_model": "The parent task ends when the claim is prepared and routed to an adjuster; final coverage and liability decisions are downstream.",
    },
}

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


def cached_task_differences(case_key: str) -> dict[str, dict[str, str]]:
    """Report differences without changing the cached transformation artifact."""

    _artifact, result = load_cached_transformation(case_key)
    cached_task = result.task_decomposition.operational_decomposition.task
    expected = TASK_CASES[case_key]
    differences = {}
    for field in ("task_name", "task_description"):
        cached_value = getattr(cached_task, field)
        expected_value = expected[field]
        if cached_value != expected_value:
            differences[field] = {
                "cached": cached_value or "",
                "task_case": expected_value,
            }
    return differences


def build_evaluation_request(
    case_key: str,
) -> TransformationSemanticEvaluationRequest:
    """Build the evaluator request from the frozen cached result only."""

    _, result = load_cached_transformation(case_key)
    task_case = TASK_CASES[case_key]

    task = result.task_decomposition.operational_decomposition.task.model_copy(
        update={
            "task_name": task_case["task_name"],
            "task_description": task_case["task_description"],
        }
    )
    request = TransformationSemanticEvaluationRequest(
        task=task,
        transformation_context={
            "domain": task_case["domain"],
            "operating_model": task_case["operating_model"],
        },
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
    differences = cached_task_differences(case_key)
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
        "task_definition_differences": differences,
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
    differences = cached_task_differences(case_key)
    result = provider.evaluate(request)
    evaluation = SemanticEvaluation.model_validate(result)
    provenance = evaluation.evaluator_provenance
    return {
        "case_key": case_key,
        "status": "evaluated",
        "task_definition_differences": differences,
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
    failed = False
    for case_key in cases:
        try:
            report = live_case(case_key, provider)
        except Exception as exc:  # noqa: BLE001 - preserve per-case provider failures
            failed = True
            report = {
                "case_key": case_key,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "expected_behavior": EXPECTED_BEHAVIOR[case_key]["description"],
            }
        print(json.dumps(report, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
