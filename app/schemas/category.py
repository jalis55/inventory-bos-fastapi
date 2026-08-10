from pydantic import BaseModel,Field,ConfigDict
from datetime import datetime


class CategoryCreate(BaseModel):
    name:str = Field(...,min_length=1,max_length=50)

    model_config=ConfigDict(from_attributes=True)


class CategoryOut(BaseModel):
    id:int
    name:str
    created_at:datetime

    model_config=ConfigDict(from_attributes=True)

class PaginatedCategories(BaseModel):
    total:int
    skip:int
    limit:int
    items:list[CategoryOut]

    model_config=ConfigDict(from_attributes=True)