"""Small portable provenance references; persistence remains host-owned."""

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1)
    value: str = Field(min_length=1)
