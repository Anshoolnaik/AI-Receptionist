"""POST /ask — Data Assistant (Part B)."""
from fastapi import APIRouter, HTTPException
from app.models import Ask, AskResponse
from app.assistant.router import route_question
from app.assistant.rag import rag_answer
from app.assistant.nl_to_sql import nl_to_sql_answer, BlockedQueryError, SchemaViolationError

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(req: Ask):
    """
    Route question to RAG (product-help) or NL→SQL (data).
    Tenant scope is enforced in code — never trusted to the LLM.
    """
    route = route_question(req.question)

    if route == "rag":
        result = rag_answer(req.question)
        return AskResponse(
            answer=result.get("answer"),
            source=result.get("source"),
            refused=result.get("refused", False),
            note=result.get("note"),
        )

    # NL→SQL path
    try:
        result = nl_to_sql_answer(req.question, req.property_id)
        return AskResponse(
            answer=result.get("answer"),
            sql=result.get("sql"),
            rows=result.get("rows", []),
            refused=result.get("refused", False),
        )
    except BlockedQueryError as e:
        raise HTTPException(status_code=400, detail=f"Blocked: {e}")
    except SchemaViolationError as e:
        raise HTTPException(status_code=400, detail=f"Schema violation: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant error: {e}")
