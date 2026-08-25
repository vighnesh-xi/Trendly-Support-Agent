# Trendly Customer Support Agent — Solution

## 1. Overview

Trendly is a direct-to-consumer fashion retailer handling around 2,000 customer support chats per day. A large portion of these conversations are repetitive, such as:

* Checking order status
* Understanding shipping updates
* Asking about returns and exchanges
* Checking refund policies
* Asking whether an item is eligible for return or exchange

The goal of this solution is to build an AI customer-support agent that can independently resolve approximately 70% of these repetitive conversations while safely handing more complex cases to a human agent.

The solution uses a **single LLM-powered agent with real tool calling**.

The LLM is responsible for understanding the conversation, deciding which action is required, calling the appropriate tool, interpreting the result, and responding naturally to the customer.

The tools are responsible for enforcing business rules and security constraints.

---

# 2. Architecture

The system follows a simple agent + tools architecture:

```text
Customer
   |
   v
Groq LLM Agent
   |
   |-- Understand user intent
   |-- Decide whether a tool is required
   |-- Select appropriate tool
   |-- Provide structured arguments
   |
   v
Tools Layer (tools.py)
   |
   |-- Order lookup
   |-- Policy lookup
   |-- Return/exchange validation
   |-- Store credit
   |-- Damaged item handling
   |-- Authorization validation
   |
   v
Tool Result
   |
   v
Groq LLM Agent
   |
   |-- Interpret result
   |-- Continue conversation if needed
   |-- Explain result in plain language
   |-- Escalate when required
   |
   v
Customer
```

The important design decision is that the LLM does **not** directly implement business rules.

Instead:

```text
LLM = reasoning + orchestration

tools.py = business logic + validation + security
```

This makes the system easier to understand, test, and maintain.

---

# 3. Why Real Tool Calling?

The assignment specifically requires an agentic implementation rather than keyword matching with an LLM wrapped around it.

This solution therefore uses actual tool/function calling.

For example, if the customer says:

> "Where is my order ORD-123?"

The agent does not simply detect the words "where" and "order".

Instead, the LLM determines that it needs order information and calls the appropriate order lookup tool.

```text
Customer:
"Where is my order ORD-123?"

        ↓

LLM decides:
"I need order information."

        ↓

Tool call:
get_order_status(order_id="ORD-123")

        ↓

Tool result:
Order is currently out for delivery.

        ↓

LLM:
"Your order is out for delivery and should arrive soon."
```

This is genuine tool-based agent behavior.

---

# 4. Responsibilities of the LLM Agent

The Groq-powered agent is responsible for orchestration.

Its main responsibilities are:

### 4.1 Understand the user's intent

The agent identifies what the customer is trying to accomplish.

Examples:

```text
"Where is my order?"
→ Order status

"Can I return these jeans?"
→ Return eligibility

"How long do refunds take?"
→ Refund policy

"My shirt arrived damaged."
→ Damaged item handling

"I want a discount."
→ Unsupported/unauthorized request
```

### 4.2 Decide when a tool is required

The agent should not call tools unnecessarily.

For example:

```text
Customer:
"What is your return window?"

→ Policy information is required.
→ Call policy tool.
```

While:

```text
Customer:
"Thanks!"

→ No tool required.
```

### 4.3 Select the correct tool

The LLM chooses the appropriate function based on the user's request and the available tool descriptions.

### 4.4 Handle multi-turn conversations

The agent maintains the conversation context so customers do not have to repeatedly provide information.

For example:

```text
Customer:
"Where is order ORD-123?"

Agent:
"Your order is currently in transit."

Customer:
"When should I receive it?"

Agent:
"Based on the current status, it is expected to arrive soon."
```

The second question can be understood in the context of the previous order.

### 4.5 Decide when to escalate

If a request cannot be safely handled by the available tools or violates business rules, the agent should hand the conversation to a human.

---

# 5. Responsibilities of `tools.py`

`tools.py` is intentionally kept simple.

The tools contain the important business logic and validation rather than relying on the LLM to enforce those rules.

This is important because an LLM should not be trusted to independently enforce security-sensitive business rules.

For example, the LLM may reason:

```text
"The customer wants store credit."
```

But it should not decide:

```text
"Give them $100 store credit."
```

The tool should validate whether that action is actually authorized and allowed.

Therefore:

```text
LLM proposes an action
        ↓
Tool validates the action
        ↓
Tool executes or rejects it
```

---

# 6. Deterministic Date Handling

The original implementation relied on the current system date.

That can make testing unpredictable because the result of an eligibility calculation may change depending on when the test is executed.

The updated implementation makes the date deterministic.

This is important for cases such as:

```text
Order date:      2026-08-01
Current date:    fixed test date
Return window:   30 days
```

The same input should produce the same result regardless of when the program is executed.

This makes the agent:

* Easier to test
* Easier to debug
* More reproducible
* More reliable during evaluation

---

# 7. Order Status Handling

The order lookup functionality allows the agent to retrieve information about an order and explain it in customer-friendly language.

The raw backend state might contain values such as:

```text
processing
shipped
in_transit
out_for_delivery
delivered
cancelled
```

The LLM converts these technical states into natural language.

For example:

```text
Backend:
out_for_delivery

Customer-facing response:
"Your order is currently out for delivery and should arrive soon."
```

The agent should also handle edge cases rather than assuming every order follows the normal delivery flow.

Examples include:

* Cancelled orders
* Delayed shipments
* Delivered orders
* Orders with refund activity
* Orders that cannot be found

The tool provides the factual result, while the LLM explains it.

---

# 8. Policy Grounding

Policy-related answers must be grounded in the provided Trendly policy rather than generated from the model's general knowledge.

Examples include:

* Return window
* Exchange rules
* Refund timing
* Shipping policy
* Eligibility requirements

The agent should retrieve the relevant policy information and use that information to answer the customer.

The model should **not invent policies**.

For example, if the policy says:

```text
Returns are accepted within 30 days.
```

The agent should not claim:

```text
Returns are accepted within 60 days.
```

simply because that sounds reasonable.

If the provided policy does not cover a customer's request, the agent should say that the available policy does not provide enough information and escalate when appropriate.

---

# 9. Return and Exchange Eligibility

Return/exchange eligibility requires combining two sources of information:

```text
Order data
+
Policy rules
```

The LLM should not make this decision purely from its own reasoning.

For example:

```text
Customer:
"Can I return order ORD-123?"
```

The system needs to consider:

```text
Order date
Order status
Item information
Current date
Return window
Policy restrictions
```

The tool layer performs the relevant validation.

Conceptually:

```text
Order information
        +
Policy
        +
Current/fixed date
        ↓
Eligibility validation
        ↓
Eligible / Not eligible
```

The LLM then explains the result to the customer.

---

# 10. Store Credit

The updated `tools.py` includes functionality for creating store credit.

This is intentionally implemented as a tool rather than allowing the LLM to simply promise store credit.

The flow is:

```text
Customer requests store credit
        ↓
LLM identifies required action
        ↓
Store credit tool called
        ↓
Tool validates authorization/business rules
        ↓
Store credit created or request rejected
        ↓
LLM communicates result
```

This prevents the model from inventing or granting unauthorized compensation.

For example, the LLM cannot simply decide:

```text
"I'll give you $50 store credit."
```

The tool must determine whether that operation is actually permitted.

---

# 11. Damaged Item Handling

The updated implementation also includes a damaged-item tool.

A damaged item is different from a normal return request because it may require special handling.

The customer might say:

> "My dress arrived damaged."

The agent can identify this as a damaged-item case and call the corresponding tool.

The tool can then validate the request according to the available business rules.

This keeps the decision deterministic and prevents the LLM from making unsupported promises.

---

# 12. Authorization and Security

One of the important design decisions is that authorization is enforced by the tools.

The LLM should not be considered a security boundary.

For example, if an operation requires authorization:

```text
LLM
 ↓
Requests operation
 ↓
Tool verifies authorization
 ↓
Allowed → execute
Denied → reject
```

This protects against situations where the model incorrectly interprets a customer's request or attempts an action that should not be allowed.

The same principle applies to:

* Store credit
* Damaged item handling
* Return/exchange actions
* Other business-sensitive operations

---

# 13. Unauthorized Discounts

The agent should not provide discounts that are not supported by the available business rules.

For example:

```text
Customer:
"Give me a 30% discount because my order was late."
```

The agent should not invent a discount policy.

Instead, it should explain that it cannot authorize an unsupported discount and escalate the request if appropriate.

This is an example of an important guardrail:

```text
No policy → No invented action
```

---

# 14. Improved Tool Query

The query sent from the LLM to the tool layer was also improved.

A good tool query should contain enough context for the tool to perform the correct validation.

Instead of sending an ambiguous request such as:

```text
"return order"
```

the agent should provide structured and relevant information.

Conceptually:

```text
Intent:
return

Order:
ORD-123

Relevant context:
customer wants to return the item
```

This reduces ambiguity and makes the tool invocation more reliable.

The tool itself remains responsible for validating whether the operation is allowed.

---

# 15. Human Escalation

Not every conversation should be handled automatically.

The agent should escalate when:

* Required information is unavailable
* The policy does not cover the request
* A business-sensitive action is unauthorized
* The customer has a complex exception
* The tool rejects an operation that requires human intervention
* The customer explicitly asks for a human
* The agent cannot confidently resolve the issue

The escalation flow is:

```text
Customer request
      ↓
Agent attempts resolution
      ↓
Can the available tools safely resolve it?
      |
   ┌──┴──┐
   |     |
  Yes    No
   |     |
Resolve  Escalate
   |     |
   └──┬──┘
      ↓
Customer response
```

The important point is that escalation should be clean rather than leaving the customer in an ambiguous state.

For example:

> "I’m unable to resolve this request using the available account and policy information. I’ll pass this conversation to a human support agent so they can review it."

---

# 16. Multi-Turn State

The agent is designed to work across multiple turns rather than treating every message as an independent request.

Example:

```text
Customer:
"Can you check order ORD-123?"

Agent:
"Your order is currently in transit."

Customer:
"Can I return it?"

Agent:
"Once it is delivered, I can check whether it meets the return policy requirements."
```

The agent understands that "it" refers to `ORD-123`.

This is handled through conversation state/context maintained by the agent rather than manually implementing keyword matching.

---

# 17. Example Conversations

## Example 1 — Order Status

```text
Customer:
Where is my order ORD-123?

Agent:
Let me check that for you.

[Tool call: order lookup]

Agent:
Your order is currently out for delivery and should arrive soon.
```

---

## Example 2 — Return Eligibility

```text
Customer:
Can I return order ORD-123?

Agent:
I'll check the order details against our return policy.

[Tool call: order + eligibility validation]

Agent:
Yes, the order is eligible for return under the current policy.
```

---

## Example 3 — Damaged Item

```text
Customer:
My shirt arrived damaged.

Agent:
I'm sorry about that. I'll check the available damaged-item process for your order.

[Tool call: damaged item handling]

Agent:
I've recorded the damaged-item request. A support agent will review it if additional handling is required.
```

---

## Example 4 — Unauthorized Discount

```text
Customer:
My delivery was late. Give me 50% off my next order.

Agent:
I can't authorize a discount that isn't supported by Trendly's available policies. I can escalate this request to a human support agent for review.
```

---

## Example 5 — Unsupported Policy

```text
Customer:
Can I return an item after six months?

Agent:
I don't have enough information in the provided Trendly policy to confirm an exception for a six-month-old purchase. I'll escalate this to a human support agent for review.
```

---

# 18. Guardrails

The implementation uses several important guardrails.

### Guardrail 1 — No invented policy

The agent only uses the provided policy information.

### Guardrail 2 — No unauthorized actions

Business-sensitive actions are validated inside tools.

### Guardrail 3 — No invented discounts

The agent cannot create compensation simply because a customer requests it.

### Guardrail 4 — Tool validation

Tools validate inputs before performing operations.

### Guardrail 5 — Deterministic dates

Eligibility calculations use a deterministic date so tests are reproducible.

### Guardrail 6 — Human escalation

The agent does not attempt to solve every possible situation.

### Guardrail 7 — Clear customer-facing responses

Internal tool results are converted into simple, understandable language.

---

# 19. Why Business Logic Is Not in the Prompt

A major design principle is to avoid putting critical business rules only inside the system prompt.

For example, it would be unsafe to rely entirely on:

```text
"If the customer asks for a refund, check whether they are eligible."
```

The LLM could misunderstand the rule.

Instead:

```text
LLM
→ determines that eligibility must be checked

Tool
→ performs actual eligibility validation
```

This provides a stronger separation of responsibilities.

The prompt guides behavior, but the tool enforces the rule.

---

# 20. Why a Single Agent?

A multi-agent architecture is unnecessary for this assignment.

The required workflows are closely related:

```text
Order
Returns
Exchanges
Shipping
Refunds
Damaged items
Escalation
```

A single agent can orchestrate these tools effectively.

Using multiple agents would introduce additional complexity such as:

* Agent-to-agent communication
* Routing logic
* Additional state management
* More difficult debugging
* More opportunities for incorrect decisions

Therefore, the solution intentionally uses:

```text
One Agent
+
Multiple Business Tools
```

This keeps the implementation simple while still demonstrating real agentic behavior.

---

# 21. Why LangChain Is Suitable

LangChain can be used to implement the agent and tool-calling workflow.

Its main role is to provide the agent framework and integration between:

```text
LLM
+
Tools
+
Conversation messages
```

However, LangChain does not replace the business logic.

The architecture remains:

```text
LangChain / Agent
        ↓
Groq LLM
        ↓
Tool Calling
        ↓
tools.py
```

The actual business rules remain in `tools.py`.

---

# 22. Why Groq?

Groq is used as the LLM provider for the agent.

The LLM is responsible for:

* Understanding natural language
* Selecting tools
* Generating tool arguments
* Interpreting tool results
* Maintaining conversational behavior
* Producing the final response

The system is therefore not dependent on keyword matching.

---

# 23. Testing Strategy

The agent should be tested using both normal and edge-case scenarios.

### Order scenarios

* Valid order ID
* Invalid order ID
* Processing order
* Shipped order
* In-transit order
* Out-for-delivery order
* Delivered order
* Cancelled order

### Return scenarios

* Eligible return
* Return outside allowed window
* Ineligible item
* Missing order
* Already processed return

### Exchange scenarios

* Eligible exchange
* Ineligible exchange
* Exchange outside policy

### Damaged item scenarios

* Valid damaged-item request
* Missing required information
* Unauthorized operation

### Policy scenarios

* Valid policy question
* Policy question with unsupported exception
* Request for invented policy

### Security scenarios

* Unauthorized store credit
* Unauthorized discount
* Invalid tool parameters

### Conversation scenarios

* Follow-up questions
* Customer changes intent
* Customer asks for a human
* Missing information
* Multiple requests in one conversation

---

# 24. Example Tool-Calling Flow

A typical request follows this sequence:

```text
1. Customer sends message

2. Agent receives conversation

3. LLM determines intent

4. LLM selects a tool

5. LLM generates structured arguments

6. Tool validates arguments

7. Tool executes business logic

8. Tool returns structured result

9. LLM interprets result

10. LLM responds in natural language

11. If the request cannot be resolved:
       → escalate to human
```

This demonstrates an actual agentic workflow rather than a simple classification system.

---

# 25. Key Design Principle

The most important architectural principle is:

```text
LLM decides WHAT should happen.
Tools decide WHETHER it is allowed and HOW it happens.
```

For example:

```text
LLM:
"The customer wants store credit."

Tool:
"Is store credit authorized?"

Tool:
"Yes → create it."

or

Tool:
"No → reject the operation."
```

This separation makes the system more reliable and secure.

---

# 26. Final Outcome

The resulting Trendly support agent provides:

* Real LLM tool calling
* Order status lookup
* Plain-language order explanations
* Policy-grounded responses
* Return and exchange eligibility validation
* Store credit handling
* Damaged-item handling
* Authorization checks
* Deterministic date handling
* Multi-turn conversation support
* Unauthorized-action prevention
* Human escalation

The implementation deliberately keeps the architecture simple:

```text
             ┌──────────────────┐
             │     Customer     │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │   Groq Agent     │
             │                  │
             │ Reason + Route   │
             └────────┬─────────┘
                      │
              Real Tool Calling
                      │
                      ▼
             ┌──────────────────┐
             │    tools.py      │
             │                  │
             │ Business Rules   │
             │ Validation       │
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
             │   Groq Agent     │
             │                  │
             │ Explain/Respond  │
             │ or Escalate      │
             └──────────────────┘
```

This approach satisfies the core assignment requirement while avoiding unnecessary architectural complexity.
