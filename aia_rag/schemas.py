from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str = Field(description="Source id such as S1 that the quote came from")
    quote: str = Field(description="Short verbatim quote supporting the answer")


class ModelAnswer(BaseModel):
    """What the LLM must return. Validated before anything reaches the user."""
    answerable: bool
    answer: str
    citations: list[Citation] = []


class ResolvedCitation(BaseModel):
    source: str
    product: str
    page: int
    quote: str
    verified: bool  # quote really occurs in the retrieved passage


class RagResponse(BaseModel):
    question: str
    answerable: bool
    answer: str
    citations: list[ResolvedCitation] = []
    abstain_reason: str | None = None  # "no_retrieval" | "model_declined" | "invalid_output"
    top_score: float | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
