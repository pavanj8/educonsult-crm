from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StudentCreate(BaseModel):
    name: str
    email: str
    password: str
    age: int


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    age: int
    created_at: datetime
