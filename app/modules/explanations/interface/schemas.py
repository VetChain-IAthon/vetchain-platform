from typing import Literal

from pydantic import BaseModel, Field

from app.modules.explanations.domain.entities import InsightAnswer


class InsightQuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class InsightAnswerOut(BaseModel):
    text: str
    sources: list[str]
    data_origin: str

    @classmethod
    def from_domain(cls, answer: InsightAnswer) -> "InsightAnswerOut":
        return cls(text=answer.text, sources=list(answer.sources), data_origin=answer.data_origin.value)


class ReportSummaryIn(BaseModel):
    report: Literal["dashboard", "kpis", "sales", "customers", "stock", "receivables", "salespeople"]
    metrics: dict[str, float] = Field(min_length=1, max_length=12)


class ReportSummaryOut(BaseModel):
    text: str
    source: Literal["gemini", "fallback"]
