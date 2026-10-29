from task_decomposition import (
    AbsoluteEffortInput,
    ActivityEffortEstimate,
    ActivityEffortEstimation,
    AgenticTask,
    AgenticTaskSynthesis,
    BaselineSubtaskEffortEstimate,
    ClassifiedSubtask,
    EffortQuantity,
    EffortUnit,
    HumanAgentActivity,
    HumanAgentActivityCategory,
    HumanAgentActivityModel,
    OperationalDecomposition,
    OperationalSubtask,
    ParentOutputContract,
    ProviderProvenance,
    ProviderStage,
    ProviderStageResponse,
    RetainRemoveClassification,
    SupportWorkInput,
    SupportWorkInputs,
    TaskDecompositionRequest,
    TaskReference,
    TimeBasis,
    TransformationClassification,
    TransformationDecompositionRequest,
)
from task_decomposition.evaluation.contracts import (
    SemanticEvaluation,
    SemanticEvaluationDecision,
)
from task_decomposition.evaluation.rubric import SEMANTIC_EVALUATION_RUBRIC_VERSION

TASK = TaskReference(
    task_id="task-boundary",
    task_name="Process account update",
    task_description="Process a customer account update request.",
)
UNIT = EffortUnit.EFFORT
TIME = TimeBasis.PER_OPERATION


def amount(value):
    return EffortQuantity(value=value, unit=UNIT, time_basis=TIME)


def operational():
    return OperationalDecomposition(
        task=TASK,
        parent_output_contract=ParentOutputContract(
            output_unit="One account update request processed",
            completion_boundary="The account record is updated.",
            source="provider_inferred",
        ),
        baseline_effort_estimates=tuple(
            BaselineSubtaskEffortEstimate(
                subtask_id=f"sub-{index}",
                expected_occurrences_per_parent_output=1,
                active_effort_per_occurrence=amount(value),
                expected_effort_per_parent_output=amount(value),
                rationale="Usually occurs once.",
            )
            for index, value in enumerate((30, 40, 30), start=1)
        ),
        operational_subtasks=(
            OperationalSubtask(
                sequence_index=1,
                subtask_id="sub-1",
                subtask_name="Receive account request",
                description="Log the incoming customer request.",
                relative_effort_weight="0.30",
                effort_rationale="Usually occurs once.",
            ),
            OperationalSubtask(
                sequence_index=2,
                subtask_id="sub-2",
                subtask_name="Verify requester identity",
                description="Confirm the requester is authorized.",
                relative_effort_weight="0.40",
                effort_rationale="Usually occurs once.",
                depends_on=("sub-1",),
            ),
            OperationalSubtask(
                sequence_index=3,
                subtask_id="sub-3",
                subtask_name="Update account record",
                description="Apply the approved account change.",
                relative_effort_weight="0.30",
                effort_rationale="Usually occurs once.",
                depends_on=("sub-2",),
            ),
        ),
    )


def task_request():
    return TaskDecompositionRequest(task=TASK, request_id="request-1")


def transform_request(baseline):
    return TransformationDecompositionRequest(
        task_decomposition=baseline,
        accounting_input=AbsoluteEffortInput(
            baseline_human_effort=amount(100),
            retained_human_work=amount(60),
            gross_removed_work=amount(40),
            support_work=SupportWorkInputs(
                ai_interaction=SupportWorkInput(
                    value=0, basis="absolute_effort", unit=UNIT, time_basis=TIME
                ),
                ai_verification=SupportWorkInput(
                    value=0, basis="absolute_effort", unit=UNIT, time_basis=TIME
                ),
            ),
        ),
        request_id="request-1",
    )


class BoundaryProvider:
    provider_id = "boundary-provider"

    def __init__(self):
        self.calls = []

    def _response(self, stage, payload):
        return ProviderStageResponse(
            stage=stage,
            payload=payload,
            provenance=ProviderProvenance(
                provider_id=self.provider_id,
                stage=stage,
                model_id="boundary-model",
                request_id="request-1",
            ),
        )

    def generate_operational_decomposition(self, request):
        self.calls.append("task")
        return self._response(ProviderStage.OPERATIONAL_DECOMPOSITION, operational())

    def evaluate(self, request):
        return SemanticEvaluation(
            decision=SemanticEvaluationDecision.ACCEPT,
            rubric_version=SEMANTIC_EVALUATION_RUBRIC_VERSION,
        )

    def classify_retain_remove(self, request):
        self.calls.append("retain-remove")
        return self._response(
            ProviderStage.RETAIN_REMOVE_CLASSIFICATION,
            RetainRemoveClassification(
                task=TASK,
                classified_subtasks=(
                    ClassifiedSubtask(
                        subtask_id="sub-1",
                        classification=TransformationClassification.RETAIN,
                    ),
                    ClassifiedSubtask(
                        subtask_id="sub-2",
                        classification=TransformationClassification.REMOVE,
                    ),
                    ClassifiedSubtask(
                        subtask_id="sub-3",
                        classification=TransformationClassification.RETAIN,
                    ),
                ),
            ),
        )

    def synthesize_agentic_tasks(self, request):
        self.calls.append("synthesis")
        return self._response(
            ProviderStage.AGENTIC_TASK_SYNTHESIS,
            AgenticTaskSynthesis(
                task=TASK,
                agentic_tasks=(
                    AgenticTask(
                        agentic_task_id="AGT001",
                        agentic_task_name="Prepare account update assessment",
                        description="Assess the account update request.",
                        source_subtask_ids=("sub-2",),
                        required_inputs=("account request",),
                        expected_outputs=("assessment",),
                    ),
                ),
            ),
        )

    def model_human_agent_activities(self, request):
        self.calls.append("activities")
        return self._response(
            ProviderStage.HUMAN_AGENT_ACTIVITY_MODELING,
            HumanAgentActivityModel(
                task=TASK,
                activities=(
                    HumanAgentActivity(
                        activity_id="HAA001",
                        activity_name="Verify assessment",
                        description="Review the agent assessment.",
                        category=HumanAgentActivityCategory.AI_VERIFICATION,
                        agentic_task_ids=("AGT001",),
                        trigger="The agent completes the assessment.",
                        expected_action="Accept or correct the assessment.",
                    ),
                ),
            ),
        )

    def estimate_activity_effort(self, request):
        self.calls.append("activity-effort")
        return self._response(
            ProviderStage.ACTIVITY_EFFORT_ESTIMATION,
            ActivityEffortEstimation(
                task=TASK,
                activity_effort_estimates=(
                    ActivityEffortEstimate(
                        activity_id="HAA001",
                        expected_occurrences_per_parent_output=1,
                        active_effort_per_occurrence=amount(14),
                        expected_effort_per_parent_output=amount(14),
                        rationale="One review per request.",
                    ),
                ),
            ),
        )
