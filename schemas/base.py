"""Base configuration shared by all public project schemas."""

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    """Strict base model for data exchanged between team-owned modules."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )
