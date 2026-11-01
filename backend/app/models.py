from pydantic import BaseModel,Field
from typing import Literal
class SynthesisRequest(BaseModel):
 idea:str=Field(min_length=8,max_length=4000)
 constraints:str=Field(default="",max_length=4000)
 quantity:int=Field(default=100,ge=1,le=1000000)
 target_unit_cost:float=Field(default=35,gt=0,le=1000000)
class FunctionalModule(BaseModel):
 id:str
 name:Literal["Power","Processing","Sensing","Connectivity","Interface","Actuation"]
 purpose:str
 interfaces:list[str]=[]
 status:str="concept"
 parts:list[str]=[]
class DesignResponse(BaseModel):
 product_name:str
 summary:str
 assumptions:list[str]
 modules:list[FunctionalModule]
 risks:list[str]
 validation_status:str="concept_only"
 estimated_complexity:Literal["LOW","MEDIUM","HIGH"]="MEDIUM"
