# Trendly Support Agent

An AI-powered customer support agent for **Trendly**, a direct-to-consumer fashion retailer handling approximately 2,000 support chats per day.

The agent uses **Groq + real tool calling** to automate repetitive customer-support workflows such as order tracking, returns, exchanges, shipping/refund policy questions, store credit, and damaged-item handling.

The system is designed to resolve common requests automatically while safely escalating unsupported or sensitive cases to a human support agent.

---

## 🚀 Live Demo

The Trendly Support Agent is deployed as a live FastAPI service.

### Base URL

https://trendly-support-agent-nqtt.onrender.com

### Interactive API Documentation

https://trendly-support-agent-nqtt.onrender.com/docs

The `/docs` endpoint provides an interactive Swagger UI where the evaluator can directly test the agent's API endpoints.

### Example API Request

The `/chat` endpoint expects:

```json
{
  "conversation_id": "test-conversation-001",
  "customer_id": "CUST-1001",
  "message": "Where is order ORD-1001?"
}
