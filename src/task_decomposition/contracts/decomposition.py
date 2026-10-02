"""Canonical baseline work row contracts."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from task_decomposition.contracts.effort import EffortQuantity
from task_decomposition.contracts.provenance import ProvenanceRef


class TransformationClassification(str, Enum):
    RETAIN = "retain"
    REMOVE = "remove"


class TransformationRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    row_id: str = Field(min_length=1)
    classification: TransformationClassification
    effort: EffortQuantity | None = None
    subtask_effort_weight: Decimal | None = Field(default=None, ge=0)
    rationale: str | None = None
    notes: str | None = None
    provenance_refs: tuple[ProvenanceRef, ...] = ()

    @field_validator("subtask_effort_weight", mode="before")
    @classmethod
    def decimal_weight(
        cls, value: Decimal | int | float | str | None
    ) -> Decimal | None:
        return None if value is None else Decimal(str(value))
