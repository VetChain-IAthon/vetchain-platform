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
