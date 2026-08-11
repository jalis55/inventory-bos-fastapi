from pydantic import BaseModel,Field,ConfigDict
from datetime import datetime


class CompanyCreate(BaseModel):
    name:str = Field(...,min_length=1,max_length=50)

    model_config=ConfigDict(from_attributes=True)


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = Field(default=None)
    
    model_config = ConfigDict(from_attributes=True)

class CompanyOut(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedCompanies(BaseModel):
    total:int
    skip:int
    limit:int  
    items:list[CompanyOut]

    model_config=ConfigDict(from_attributes=True)

    