from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(default="Student", min_length=1, max_length=120)
    target_role: str = Field(min_length=2, max_length=160)
    job_description: str = Field(min_length=30, max_length=12000)
    resume_text: str = Field(default="", max_length=20000)
    manual_skills: list[str] = Field(default_factory=list, max_length=100)


class TaskUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1, max_length=180)
    position: str = Field(min_length=1, max_length=180)
    status: str = Field(default="Applied", max_length=30)
    applied_date: str = Field(default="", max_length=20)
    notes: str = Field(default="", max_length=2000)


class ApplicationUpdate(BaseModel):
    status: Optional[str] = Field(default=None, max_length=30)
    notes: Optional[str] = Field(default=None, max_length=2000)


class InterviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    target_role: str = Field(min_length=2, max_length=160)
    question: str = Field(min_length=5, max_length=1500)
    answer: str = Field(min_length=10, max_length=5000)
