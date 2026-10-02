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
    return value if isinstance(value, Decimal) else Decimal(str(value))


class EffortQuantity(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Decimal
    unit: EffortUnit
    time_basis: TimeBasis

    @field_validator("value", mode="before")
    @classmethod
    def non_negative(cls, value: Decimal | int | float | str) -> Decimal:
        result = _decimal(value)
        if result < 0:
            raise NegativeEffortError("effort quantities cannot be negative")
        return result


class SupportWorkInput(BaseModel):
    """One support contribution with an explicit semantic basis.

    ``value`` is interpreted according to ``basis``.  In particular,
    ``NORMALIZED_CONTRIBUTION`` is already baseline-relative and must not be
    multiplied by gross removed work a second time.
    """

    model_config = ConfigDict(frozen=True)

    value: Decimal
    basis: RatioBasis
    unit: EffortUnit | None = None
    time_basis: TimeBasis | None = None

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
    model_config = ConfigDict(frozen=True)

    governance: SupportWorkInput
    operational_support: SupportWorkInput
    lifecycle_support: SupportWorkInput


class AbsoluteEffortInput(BaseModel):
    """Absolute accounting input. Support fields may also be explicit ratios."""

    model_config = ConfigDict(frozen=True)

    baseline_human_effort: EffortQuantity
    retained_human_work: EffortQuantity
    gross_removed_work: EffortQuantity
    support_work: SupportWorkInputs


class NormalizedAccountingInput(BaseModel):
    """Baseline-relative accounting input, with W0 fixed to 1.0."""

    model_config = ConfigDict(frozen=True)

    retained_work_ratio: Decimal = Field(ge=0)
    gross_removed_work_ratio: Decimal = Field(ge=0)
    support_work: SupportWorkInputs

    @field_validator("retained_work_ratio", "gross_removed_work_ratio", mode="before")
    @classmethod
    def decimal_ratio(cls, value: Decimal | int | float | str) -> Decimal:
        result = _decimal(value)
        if result < 0:
            raise NegativeEffortError(
                "normalized effort contributions cannot be negative"
            )
        return result
