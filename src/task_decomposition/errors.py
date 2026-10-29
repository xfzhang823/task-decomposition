"""Host-neutral errors raised by the canonical accounting domain."""


class TaskDecompositionError(Exception):
    """Base class for standalone task-decomposition errors."""


class ContractValidationError(TaskDecompositionError, ValueError):
    """A contract value is malformed or uses an incompatible basis."""


class NegativeEffortError(ContractValidationError):
    """Effort and contribution values cannot be negative."""


class InvalidDenominatorError(ContractValidationError):
    """A ratio or multiplier has an invalid denominator."""


class ZeroBaselineError(InvalidDenominatorError):
    """Transformation-impact ratios require a positive baseline W0."""


class AccountingInvariantError(TaskDecompositionError, ValueError):
    """A deterministic accounting balance or component invariant failed."""


class RatioBasisError(ContractValidationError):
    """A support value has no explicit or compatible ratio basis."""


class IncompatibleEffortUnitError(ContractValidationError):
    """Absolute quantities do not share one unit/time basis."""


class StageValidationError(TaskDecompositionError, ValueError):
    """A staged provider output failed standalone validation."""


class StageDependencyError(StageValidationError):
    """A stage was supplied without a valid preceding stage result."""


class IdentityMismatchError(StageValidationError):
    """A later stage changed task or subtask identity."""


class CardinalityError(StageValidationError):
    """A stage has missing, extra, or duplicate rows."""


class UnknownReferenceError(StageValidationError):
    """A stage references an unknown task, subtask, or dependency."""


class MissingAccountingInputError(StageValidationError):
    """Staged output lacks the explicit effort needed for canonical accounting."""


class MissingEffortAllocationError(StageValidationError):
    """A reusable task baseline lacks a complete effort allocation."""


class SupportBasisConflictError(StageValidationError):
    """Rows in one support category cannot be combined without a common basis."""


class ProviderError(TaskDecompositionError):
    """Base class for provider-boundary failures exposed by the application."""


class ProviderExecutionError(ProviderError):
    """A provider failed while generating a requested stage."""


class ProviderOutputError(ProviderError):
    """A provider returned an invalid or incorrectly labeled response envelope."""


class ProviderContractValidationError(ProviderOutputError):
    """Provider payload failed structural stage validation."""


class ProviderSemanticValidationError(ProviderOutputError):
    """A valid evaluator decision rejected or could not repair a decomposition."""

    def __init__(
        self,
        message: str,
        *,
        validation_errors=(),
        rejected_response=None,
        repair_attempts: int = 0,
        final_response=None,
        semantic_findings=(),
    ):
        super().__init__(message)
        self.validation_errors = tuple(validation_errors)
        self.rejected_response = rejected_response
        self.repair_attempts = repair_attempts
        self.final_response = final_response
        self.semantic_findings = tuple(semantic_findings)


class ProviderConfigurationError(ProviderError):
    """A concrete provider is not configured for execution."""


class ProviderAuthenticationError(ProviderError):
    """A concrete provider rejected authentication."""


class SemanticEvaluatorUnavailableError(ProviderConfigurationError):
    """No evaluator capability was configured for operational evaluation."""


class SemanticEvaluatorContractError(ProviderOutputError):
    """An injected evaluator returned a malformed or inconsistent result."""
