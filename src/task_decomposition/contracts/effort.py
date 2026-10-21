"""Portable effort and ratio-basis value objects."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from task_decomposition.errors import ContractValidationError, NegativeEffortError


class EffortUnit(str, Enum):
    """Generic effort units; the domain does not require hours."""

    EFFORT = "effort"
    HOURS = "hours"
    DAYS = "days"
    FTE = "fte"


class TimeBasis(str, Enum):
    """The period over which an absolute effort quantity is measured."""

    PER_OPERATION = "per_operation"
    PER_DAY = "per_day"
    PER_WEEK = "per_week"
    PER_MONTH = "per_month"
    PER_YEAR = "per_year"


class RatioBasis(str, Enum):
    """Explicit denominators/meaning for a support input."""

    RATIO_OF_BASELINE_WORK = "ratio_of_baseline_work"
    RATIO_OF_GROSS_REMOVED_WORK = "ratio_of_gross_removed_work"
    NORMALIZED_CONTRIBUTION = "normalized_contribution"
    ABSOLUTE_EFFORT = "absolute_effort"


def _decimal(value: Decimal | int | float | str) -> Decimal:
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ContractValidationError("effort values must be finite")
    return result


class EffortQuantity(BaseModel):
    """A non-negative effort quantity with explicit unit and time basis.

    ``value`` is an amount of effort, not a ratio.  ``unit`` and
    ``time_basis`` must be compatible before quantities are added or compared.
    The accounting domain uses these quantities for absolute baseline,
    retained, removed, and resolved support work.
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal = Field(description="Non-negative effort amount.")
    unit: EffortUnit = Field(
        description="Unit in which the effort amount is expressed."
    )
    time_basis: TimeBasis = Field(
        description="Period or execution basis represented by the amount."
    )

    @field_validator("value", mode="before")
    @classmethod
    def non_negative(cls, value: Decimal | int | float | str) -> Decimal:
        result = _decimal(value)
        if result < 0:
            raise NegativeEffortError("effort quantities cannot be negative")
        return result


class SupportWorkInput(BaseModel):
    """One additional human support contribution with an explicit basis.

    ``value`` is interpreted according to ``basis``.  In particular,
    ``NORMALIZED_CONTRIBUTION`` is already baseline-relative and must not be
    multiplied by gross removed work a second time.  Support work is
    post-transformation effort; it is not part of the original baseline
    partition into retained and gross-removed work.
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal = Field(
        description="Non-negative additional support effort or ratio."
    )
    basis: RatioBasis = Field(
        description="Denominator and interpretation for ``value``."
    )
    unit: EffortUnit | None = Field(
        default=None,
        description="Required only when basis is ABSOLUTE_EFFORT.",
    )
    time_basis: TimeBasis | None = Field(
        default=None,
        description="Required only when basis is ABSOLUTE_EFFORT.",
    )

    @field_validator("value", mode="before")
    @classmethod
    def non_negative(cls, value: Decimal | int | float | str) -> Decimal:
        result = _decimal(value)
        if result < 0:
            raise NegativeEffortError("support contributions cannot be negative")
        return result

    @model_validator(mode="after")
    def validate_absolute_metadata(self) -> "SupportWorkInput":
        if self.basis is RatioBasis.ABSOLUTE_EFFORT:
            if self.unit is None or self.time_basis is None:
                raise ContractValidationError(
                    "absolute support effort requires unit and time_basis"
                )
        elif self.unit is not None or self.time_basis is not None:
            raise ContractValidationError(
                "unit/time_basis are only valid for absolute support effort"
            )
        return self


class SupportWorkInputs(BaseModel):
    """Canonical categories of additional human support work.

    ``ai_interaction`` covers human effort to interact with or operate the AI
    system.  ``ai_verification`` covers human effort to check, validate, or
    approve AI-related output.  The application resolves these contributions
    before deterministic accounting.
    """

    model_config = ConfigDict(frozen=True)

    ai_interaction: SupportWorkInput = Field(
        description="Additional human effort for AI interaction or operation."
    )
    ai_verification: SupportWorkInput = Field(
        description="Additional human effort for AI-output verification or approval."
    )


class AbsoluteEffortInput(BaseModel):
    """Absolute inputs for canonical W0/W1 accounting.

    ``baseline_human_effort`` is the total human effort required before the
    transformation.  It is not an additional component to add to retained or
    removed work.  ``retained_human_work`` is the portion of that baseline
    associated with RETAIN subtasks, and ``gross_removed_work`` is the portion
    associated with REMOVE subtasks before newly introduced support work is
    considered.  Therefore the baseline partition is
    ``W0 = retained_human_work + gross_removed_work``.

    ``support_work`` contains additional post-transformation human effort.
    It may use absolute effort or an explicitly declared ratio basis.  The
    application normally resolves this field before handing the input to the
    deterministic accounting domain.
    """

    model_config = ConfigDict(frozen=True)

    baseline_human_effort: EffortQuantity = Field(
        description=(
            "Total human effort before AI transformation; this is W0, "
            "not an additive component."
        )
    )
    retained_human_work: EffortQuantity = Field(
        description="Baseline effort belonging to subtasks classified RETAIN."
    )
    gross_removed_work: EffortQuantity = Field(
        description=(
            "Baseline effort belonging to subtasks classified REMOVE, "
            "before support work."
        )
    )
    support_work: SupportWorkInputs | None = Field(
        default=None,
        description=(
            "Additional post-transformation human support effort, "
            "resolved by the application."
        ),
    )


class NormalizedAccountingInput(BaseModel):
    """Baseline-relative inputs for canonical W0/W1 accounting.

    This representation fixes the baseline to ``W0 = 1.0``.  The retained and
    gross-removed fields are fractions of the original baseline and must
    partition that baseline within the accounting tolerance.  They are not
    post-transformation effort.  ``support_work`` represents additional
    post-transformation human effort and must use a compatible non-absolute
    ratio basis; absolute support effort is rejected by normalized accounting.
    """

    model_config = ConfigDict(frozen=True)

    retained_work_ratio: Decimal = Field(
        ge=0, description="Fraction of baseline human effort that remains RETAIN work."
    )
    gross_removed_work_ratio: Decimal = Field(
        ge=0,
        description=(
            "Fraction of baseline human effort classified REMOVE before support work."
        ),
    )
    support_work: SupportWorkInputs | None = Field(
        default=None,
        description=(
            "Additional post-transformation support contributions in explicit "
            "ratio bases."
        ),
    )

    @field_validator("retained_work_ratio", "gross_removed_work_ratio", mode="before")
    @classmethod
    def decimal_ratio(cls, value: Decimal | int | float | str) -> Decimal:
        result = _decimal(value)
        if result < 0:
            raise NegativeEffortError(
                "normalized effort contributions cannot be negative"
            )
        return result
