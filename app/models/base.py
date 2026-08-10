from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Base API model that rejects non-finite JSON numbers."""

    model_config = ConfigDict(allow_inf_nan=False)
