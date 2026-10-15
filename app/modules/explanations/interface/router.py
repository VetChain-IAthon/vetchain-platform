from fastapi import APIRouter, Depends

from app.core.application import MANAGER, SessionUser
from app.core.auth import require_role
from app.modules.explanations.application import use_cases as uc
from app.modules.explanations.interface import dependencies as deps
from app.modules.explanations.interface.schemas import InsightAnswerOut, InsightQuestionIn, ReportSummaryIn, ReportSummaryOut
from app.modules.explanations.application.report_summary import ExplainReport

router = APIRouter(tags=["preguntas a los datos"])


@router.post("/insights/questions", response_model=InsightAnswerOut)
def ask_insight_question(
    body: InsightQuestionIn,
    _: SessionUser = Depends(require_role(MANAGER)),
    use_case: uc.AskInsightQuestion = Depends(deps.get_ask_insight_question),
):
    """Pregunta en lenguaje natural. Gemini solo elige una consulta permitida; las cifras salen de la base."""
    return InsightAnswerOut.from_domain(use_case.execute(body.question))


@router.post("/insights/report-summary", response_model=ReportSummaryOut)
def summarize_report(
    body: ReportSummaryIn,
    _: SessionUser = Depends(require_role(MANAGER)),
):
    """Envía a Gemini únicamente las métricas numéricas permitidas del reporte."""
    return ExplainReport(deps.text_generator()).execute(body.report, body.metrics)
