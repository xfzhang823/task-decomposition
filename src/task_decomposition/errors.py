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
