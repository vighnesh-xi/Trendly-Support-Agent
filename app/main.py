from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agent import chat


app = FastAPI(
    title="Trendly Support Agent",
    description="Agentic customer support assistant for the Trendly FDE assignment.",
    version="1.0.0",
)

# Request / Response models

class ChatRequest(BaseModel):
    conversation_id: str = Field(
        ...,
        description="Unique ID for the conversation."
    )

    customer_id: str = Field(
        ...,
        description="Authenticated Trendly customer ID."
    )

    message: str = Field(
        ...,
        min_length=1,
        description="Customer message."
    )


class ChatResponse(BaseModel):
    conversation_id: str
    response: str

# Health check

@app.get("/")
def root():
    return {
        "service": "Trendly Support Agent",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# Chat endpoint

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):

    try:
        response = chat(
            conversation_id=request.conversation_id,
            customer_id=request.customer_id,
            message=request.message,
        )

        return ChatResponse(
            conversation_id=request.conversation_id,
            response=response,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:
        print(f"Agent error: {exc}")
        return ChatResponse(
            conversation_id=request.conversation_id,
            response=(
                "I'm having trouble processing your request right now. "
                "I don't want to give you incorrect information. "
                "Please try again, or I can connect you with a human "
                "support agent."
            ),
        )