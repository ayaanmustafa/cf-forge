# backend/schemas.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ProblemOut(BaseModel):
    id: int
    contest_id: int
    index: str
    name: str
    rating: Optional[int]

    class Config:
        from_attributes = True


class TagOut(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


class ProblemTagOut(BaseModel):
    id: int
    tag: TagOut

    class Config:
        from_attributes = True


class SolvedProblemOut(BaseModel):
    id: int
    solved_at: datetime
    cf_submission_id: Optional[int]
    user_note: Optional[str]
    user_solution_code: Optional[str]
    problem: ProblemOut
    tags: List[ProblemTagOut] = []

    class Config:
        from_attributes = True