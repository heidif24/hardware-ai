from pydantic import BaseModel, Field
from typing import Literal

class SynthesisRequest(BaseModel):
    idea: str = Field(min_length=8, max_length=4000)
    constraints: str = Field(default="", max_length=4000)
    quantity: int = Field(default=100, ge=1, le=1000000)

class FunctionalModule(BaseModel):
    id: str
    name: Literal["Power", "Processing", "Sensing", "Connectivity", "Interface", "Actuation"]
    purpose: str
    interfaces: list[str] = Field(default_factory=list)
    status: str = "concept"
    parts: list[str] = Field(default_factory=list)

class DesignResponse(BaseModel):
    product_name: str
    summary: str
    assumptions: list[str] = Field(default_factory=list)
    modules: list[FunctionalModule]
    risks: list[str] = Field(default_factory=list)
    validation_status: str = "concept_only"
    estimated_complexity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    requirements: list[str] = Field(default_factory=list)
    electrical_design: list[str] = Field(default_factory=list)
    interface_control: list[str] = Field(default_factory=list)
    firmware_plan: list[str] = Field(default_factory=list)
    mechanical_plan: list[str] = Field(default_factory=list)
    verification_plan: list[str] = Field(default_factory=list)
