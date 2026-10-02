"""Optional benchmark lookup extension; no external integration is included."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from task_decomposition.contracts.provenance import ProvenanceRef


class BenchmarkQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_name: str = Field(min_length=1)
    task_description: str | None = None
    context: dict[str, str] = Field(default_factory=dict)


class BenchmarkReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    provenance_refs: tuple[ProvenanceRef, ...] = ()


@runtime_checkable
class BenchmarkProvider(Protocol):
    """Optional benchmark retrieval; never required for decomposition."""

    def retrieve(self, query: BenchmarkQuery) -> tuple[BenchmarkReference, ...]: ...


__all__ = ["BenchmarkProvider", "BenchmarkQuery", "BenchmarkReference"]
