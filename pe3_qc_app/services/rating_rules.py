"""Persisted contracts for rating points attached to saved QC tolerance limits."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TolerancePointsRule(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    type: Literal["custom_tolerance_points_v1"]
    max_points: float = Field(gt=0, le=1_000_000)
    warn_low_points: float = Field(ge=0)
    warn_high_points: float = Field(ge=0)
    alarm_low_points: float = Field(ge=0)
    alarm_high_points: float = Field(ge=0)

    @model_validator(mode="after")
    def points_within_maximum(self):
        for bound in ("warn_low", "warn_high", "alarm_low", "alarm_high"):
            if getattr(self, f"{bound}_points") > self.max_points:
                raise ValueError(f"{bound}_points must be between 0 and Max points.")
        return self
