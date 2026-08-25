# Trendly Support Agent

An AI-powered customer support agent for **Trendly**, a direct-to-consumer fashion retailer handling approximately 2,000 support chats per day.

The agent uses **Groq + real tool calling** to automate repetitive customer-support workflows such as order tracking, returns, exchanges, shipping/refund policy questions, store credit, and damaged-item handling.

The system is designed to resolve common requests automatically while safely escalating unsupported or sensitive cases to a human support agent.

---

## Features

* 🔎 Order status lookup
* 📦 Plain-language order status explanations
* 🚚 Shipping and delivery policy questions
* 🔄 Return and exchange eligibility
* 💰 Refund policy questions
* 🎟️ Store credit handling
* 📦 Damaged-item handling
* 🔐 Authorization and business-rule validation
* 🛡️ Protection against unauthorized discounts/actions
* 📚 Policy-grounded responses
* 💬 Multi-turn conversations
* 👤 Human escalation for unsupported/complex cases
* 🗓️ Deterministic date handling for reproducible testing
* 🧰 Real LLM tool/function calling

---

## Architecture

```text
                         ┌──────────────────┐
                         │     Customer     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Groq LLM Agent │
                         │                  │
                         │ Intent + Reason  │
                         │ Tool Selection   │
                         │ Tool Arguments   │
                         └────────┬─────────┘
                                  │
                           Real Tool Calling
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    tools.py      │
                         │                  │
                         │ Order Lookup     │
                         │ Policy Rules     │
                         │ Eligibility      │
                         │ Store Credit     │
                         │ Damaged Items    │
                         │ Authorization    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Tool Result    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Groq LLM Agent │
                         │                  │
                         │ Explain Result   │
                         │ Continue/Ask     │
                         │ Escalate         │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     Customer     │
                         └──────────────────┘
```

### Core design principle

> **The LLM decides what action is needed. The tools decide whether that action is allowed and perform the business operation.**

This prevents critical business rules from being dependent solely on LLM reasoning.

---

## Project Structure

```text
trendly-support-agent/
│
├── agent.py
├── tools.py
├── policy.md
├── requirements.txt
├── .env
├── .gitignore
├── README.md
└── solution.md
```

### `agent.py`

Contains the Groq-powered agent and orchestration logic.

Responsibilities include:

* Understanding customer messages
* Selecting tools
* Generating tool arguments
* Handling tool results
* Maintaining conversation context
* Generating customer-facing responses
* Escalating when necessary

### `tools.py`

Contains the business actions and validation logic.

This is the most important safety boundary in the application.

Responsibilities include:

* Order lookup
* Policy-related operations
* Return/exchange validation
* Store credit
* Damaged-item handling
* Authorization checks
* Business-rule enforcement

### `policy.md`

Contains the provided Trendly customer-support policy.

Policy-related answers should be grounded in this document rather than generated from general model knowledge.

### `solution.md`

Contains the detailed design decisions and explanation of the implementation.

---

# How the Agent Works

A typical interaction follows this flow:

```text
Customer message
      │
      ▼
LLM understands request
      │
      ▼
Does it need a tool?
      │
   ┌──┴──┐
   │     │
  No    Yes
   │     │
   │     ▼
   │   Tool call
   │     │
   │     ▼
   │   Validation
   │     │
   │     ▼
   │   Tool result
   │     │
   └──┬──┘
      ▼
LLM generates response
      │
      ▼
Customer
```

If the request cannot be safely resolved:

```text
Customer
   │
   ▼
Agent
   │
   ▼
Cannot safely resolve
   │
   ▼
Human escalation
```

---

# Real Tool Calling

This project does **not** use keyword matching with an LLM response layered on top.

The LLM has access to actual tools and decides when to call them.

For example:

```text
Customer:
"Where is order ORD-1001?"
```

The agent can decide to call:

```text
get_order_status(order_id="ORD-1001")
```

The tool returns structured information.

The LLM then converts that result into a natural response:

```text
"Your order is currently out for delivery and should arrive soon."
```

This separation allows the LLM to focus on reasoning and conversation while the tools enforce the actual business rules.

---

# Available Tool Categories

The exact tool definitions are implemented in `tools.py`.

The main capabilities include:

### Order lookup

Retrieves order information required to answer status and eligibility questions.

### Policy handling

Provides information required to answer questions about Trendly's policies.

### Return/exchange validation

Combines order information with policy rules to determine whether a request is eligible.

### Store credit

Handles store-credit creation through a controlled business action rather than allowing the LLM to invent compensation.

### Damaged item

Handles customer reports involving damaged products.

### Authorization

Validates whether sensitive business actions are permitted.

---

# Business Logic and Security

Business rules are intentionally implemented in `tools.py`.

The LLM should not independently decide whether a sensitive operation is allowed.

For example:

```text
Customer:
"Give me $50 store credit."

        ↓

LLM:
Customer wants store credit.

        ↓

Tool:
Validate request + authorization.

        ↓

Allowed?
   │
 ┌─┴─┐
Yes  No
 │    │
 ▼    ▼
Create  Reject
credit  operation
```

This prevents the model from accidentally granting unauthorized compensation.

The same principle applies to other sensitive operations.

---

# Policy Grounding

The agent should only provide policy information supported by the provided Trendly policy.

For example, if the policy specifies a return window, the agent can use that rule to answer return questions.

It should **not invent additional rules**.

If a customer asks for an exception that is not covered by the available policy, the agent should avoid guessing and escalate when necessary.

Example:

```text
Customer:
"Can I return this after six months?"

Agent:
"I don't have enough information in the provided policy to confirm
an exception for this case. I'll escalate this to a human support
agent for review."
```

---

# Return and Exchange Eligibility

Eligibility is not decided purely by the LLM.

The system combines:

```text
Order data
     +
Policy rules
     +
Deterministic date
     ↓
Eligibility validation
```

This allows the same input to produce the same result during testing.

Example:

```text
Order date:       2026-08-01
Current date:     Fixed test date
Return window:    Policy-defined window

                ↓

        Eligibility check
```

---

# Deterministic Date

The application avoids relying on an uncontrolled system date for eligibility calculations.

Using a deterministic date makes testing:

* Reproducible
* Predictable
* Easier to debug
* Independent of the day on which the test runs

This is particularly important for return-window calculations.

---

# Store Credit

Store credit is implemented as a controlled tool action.

The LLM cannot simply promise a customer an arbitrary amount.

Instead:

```text
Customer request
       ↓
LLM identifies store-credit intent
       ↓
Store-credit tool
       ↓
Authorization/business validation
       ↓
Create or reject
       ↓
LLM explains result
```

This keeps compensation decisions inside the business-logic layer.

---

# Damaged Items

Damaged-item requests have their own tool flow because they may require handling that differs from a normal return.

Example:

```text
Customer:
"My shirt arrived damaged."

        ↓

LLM identifies damaged-item intent

        ↓

Damaged-item tool

        ↓

Validation/business rules

        ↓

Result

        ↓

Customer-facing response
```

If additional human review is required, the agent escalates the conversation.

---

# Human Escalation

The agent should not attempt to solve every request.

It should escalate when:

* The customer explicitly requests a human
* Required information is missing
* The policy does not cover the request
* A sensitive action is unauthorized
* A business exception requires human approval
* A tool rejects an operation requiring manual handling
* The agent cannot safely determine the answer

Example:

```text
Customer:
"I want an exception to your return policy."

Agent:
"I’m unable to confirm an exception using the available policy
information. I’ll escalate this to a human support agent for review."
```

---

# Guardrails

The application follows several important guardrails.

| Guardrail              | Purpose                             |
| ---------------------- | ----------------------------------- |
| Policy grounding       | Prevent invented policies           |
| Tool validation        | Enforce business rules              |
| Authorization checks   | Protect sensitive actions           |
| Deterministic date     | Reproducible eligibility decisions  |
| No arbitrary discounts | Prevent unauthorized compensation   |
| Human escalation       | Handle unsupported/complex requests |
| Structured tool calls  | Reduce ambiguous tool inputs        |

---

# Multi-Turn Conversations

The agent supports contextual conversations.

Example:

```text
Customer:
"Check order ORD-1001."

Agent:
"Your order is currently in transit."

Customer:
"Can I return it?"

Agent:
"I can check whether that order meets the return policy requirements."
```

The second message can be interpreted using the previous conversation context.

The agent does not require the customer to repeat the order ID unnecessarily.

---

# Example Scenarios

## 1. Order Status

```text
User:
Where is order ORD-1001?

Agent:
Let me check that for you.

[Tool call]

Agent:
Your order is currently in transit.
```

---

## 2. Return Eligibility

```text
User:
Can I return order ORD-1001?

Agent:
I'll check the order against our return policy.

[Tool call]

Agent:
The order is eligible for return under the current policy.
```

---

## 3. Damaged Item

```text
User:
My order arrived damaged.

Agent:
I'm sorry about that. I'll check the damaged-item handling process.

[Tool call]

Agent:
I've recorded the damaged-item request. If additional review
is required, I'll connect you with a human support agent.
```

---

## 4. Unauthorized Discount

```text
User:
Give me 50% off because my order was late.

Agent:
I can't authorize a discount that isn't supported by the
available Trendly policies. I can escalate this request
to a human support agent for review.
```

---

## 5. Unsupported Policy Question

```text
User:
Can I return an item after six months?

Agent:
I don't have enough information in the provided policy to
confirm an exception for this case. I'll escalate this
to a human support agent for review.
```

---

# Setup

## 1. Clone the repository

```bash
git clone <repository-url>
cd trendly-support-agent
```

## 2. Create a virtual environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
```

Do not commit the `.env` file to Git.

---

# Running the Agent

Run the application using:

```bash
python agent.py
```

The agent can then be used interactively to simulate customer-support conversations.

Example:

```text
You: Where is order ORD-1001?

Agent: Your order is currently out for delivery and should arrive soon.

You: Can I return it?

Agent: I'll check the return eligibility for that order.
```

---

# Testing

The implementation should be tested against both normal and edge cases.

### Order tests

```text
Valid order
Invalid order
Processing
Shipped
In transit
Out for delivery
Delivered
Cancelled
```

### Return/exchange tests

```text
Eligible return
Expired return window
Ineligible item
Eligible exchange
Ineligible exchange
Missing order
```

### Policy tests

```text
Known policy question
Unknown policy question
Unsupported exception
```

### Business-action tests

```text
Authorized store credit
Unauthorized store credit
Damaged item
Unauthorized operation
```

### Agent behavior tests

```text
Multi-turn conversation
Missing information
Multiple requests
Explicit human escalation
Unsupported request
Unauthorized discount
```

---

# Design Decisions

## Why one agent?

The problem domain is small enough that a single agent can effectively orchestrate the required tools.

A multi-agent architecture would add unnecessary routing and state complexity.

## Why tools?

Tools provide deterministic business operations and prevent the LLM from directly controlling sensitive actions.

## Why keep business logic in `tools.py`?

Because business rules should be deterministic, testable, and independent of model behavior.

## Why use the LLM for orchestration?

Natural-language intent detection, tool selection, contextual reasoning, and customer-facing responses are areas where an LLM provides significant value.

## Why not keyword matching?

Keyword matching does not provide robust intent understanding or multi-turn reasoning and would not satisfy the requirement for genuine agentic tool calling.

---

# Technology Stack

| Component     | Technology                   |
| ------------- | ---------------------------- |
| Language      | Python                       |
| LLM           | Groq                         |
| Agent         | LLM-based tool-calling agent |
| Tools         | Python functions             |
| Policy        | Markdown document            |
| Environment   | Python virtual environment   |
| Configuration | `.env`                       |

---

# Security Philosophy

The application follows a simple principle:

```text
Never trust the LLM with critical business decisions.
```

The model can suggest an action, but the application validates that action before executing it.

```text
             LLM
              │
              │ "Perform action X"
              ▼
        ┌─────────────┐
        │  Validation │
        └──────┬──────┘
               │
        ┌──────┴──────┐
        │             │
      Allowed       Denied
        │             │
        ▼             ▼
     Execute       Reject
```

This makes the system safer than relying solely on prompt instructions.

---

# Assignment Requirements Coverage

| Requirement            | Implementation                      |
| ---------------------- | ----------------------------------- |
| Real agentic behavior  | Groq LLM with real tool calling     |
| Order lookup           | Order tool in `tools.py`            |
| Plain-language status  | LLM interprets tool results         |
| Policy questions       | Grounded in `policy.md`             |
| Return eligibility     | Order + policy + deterministic date |
| Exchange eligibility   | Order + policy validation           |
| Store credit           | Dedicated store-credit tool         |
| Damaged items          | Dedicated damaged-item tool         |
| Authorization          | Validation inside tools             |
| Unauthorized discounts | Refused/escalated                   |
| Edge cases             | Tool validation + escalation        |
| Multi-turn state       | Agent conversation context          |
| Human handoff          | Explicit escalation behavior        |
| Deterministic testing  | Fixed date                          |
| Business logic         | `tools.py`                          |

---

# Summary

Trendly Support Agent uses a simple but robust architecture:

```text
        Groq LLM
           │
           │ Reason + Select Tool
           ▼
        tools.py
           │
           │ Validate + Execute
           ▼
       Tool Result
           │
           ▼
        Groq LLM
           │
           ├── Respond
           │
           └── Escalate
```

The key architectural separation is:

> **The agent handles reasoning and orchestration, while `tools.py` enforces business logic, validation, and security.**

This allows the system to automate common Trendly support requests while remaining deterministic and safe for sensitive business operations.
