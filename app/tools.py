import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


# ============================================================
# PATHS / CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ORDERS_FILE = BASE_DIR / "data" / "orders.json"
POLICY_FILE = BASE_DIR / "data" / "trendly_policy.md"

# Can be overridden for deterministic testing:
# TRENDLY_CURRENT_DATE=2026-08-25
CURRENT_DATE = date.fromisoformat(
    os.getenv(
        "TRENDLY_CURRENT_DATE",
        date.today().isoformat()
    )
)


# ============================================================
# DATA LOADING
# ============================================================

def _load_orders() -> list:
    """Load Trendly's fixed orders from orders.json."""

    with open(ORDERS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Support either:
    # [{"order_id": ...}, ...]
    # or {"orders": [...]}
    if isinstance(data, dict):
        return data.get("orders", [])

    return data


def _load_policy() -> str:
    """Load Trendly's policy document."""

    with open(POLICY_FILE, "r", encoding="utf-8") as file:
        return file.read()


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _find_order(order_id: str) -> Optional[dict]:
    """Find an order by order ID."""

    orders = _load_orders()

    for order in orders:
        if order.get("order_id", "").upper() == order_id.upper():
            return order

    return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Safely parse an ISO date/datetime."""

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()

    except (ValueError, TypeError):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None


def _days_since_delivery(order: dict) -> Optional[int]:
    """Return number of calendar days since delivery."""

    delivered = _parse_date(order.get("delivered_at"))

    if delivered is None:
        return None

    return (CURRENT_DATE - delivered).days


def _is_within_return_window(order: dict) -> bool:
    """Check whether an order is within the 30-day return window."""

    days = _days_since_delivery(order)

    if days is None:
        return False

    return 0 <= days <= 30


def _get_items(order: dict) -> list:
    """Safely get order items."""

    items = order.get("items", [])

    if isinstance(items, list):
        return items

    return []


def _is_jewellery(item: dict) -> bool:
    """Check whether an item belongs to jewellery."""

    category = str(item.get("category", "")).lower()

    return "jewellery" in category or "jewelry" in category


def _is_final_sale(item: dict) -> bool:
    """Check whether an item is final sale."""

    return item.get("final_sale") is True


def _has_non_returnable_category(item: dict) -> bool:
    """Check policy-defined non-returnable categories."""

    category = str(item.get("category", "")).lower()

    non_returnable_keywords = {
        "jewellery",
        "jewelry",
    }

    return category in non_returnable_keywords


def _order_belongs_to_customer(
    order: dict,
    customer_id: str
) -> bool:
    """Verify order ownership."""

    return order.get("customer_id") == customer_id


# ============================================================
# EXCHANGE STATE
# ============================================================

# Prototype-only in-memory exchange history.
#
# In production this would be stored in a database.
EXCHANGE_HISTORY = set()


# ============================================================
# TOOL 1: ORDER LOOKUP
# ============================================================

def make_get_order_tool(customer_id: str):

    @tool
    def get_order(order_id: str) -> str:
        """
        Look up an authenticated customer's order.

        Returns order status, delivery information, tracking,
        items and other available order information.

        Never use this tool to access another customer's order.
        """

        order = _find_order(order_id)

        if order is None:
            return json.dumps({
                "success": False,
                "error": "ORDER_NOT_FOUND",
                "message": f"No order was found with ID {order_id}."
            })

        # SECURITY CHECK
        if not _order_belongs_to_customer(order, customer_id):
            return json.dumps({
                "success": False,
                "error": "ORDER_ACCESS_DENIED",
                "message": (
                    "This order does not belong to the authenticated "
                    "customer."
                )
            })

        return json.dumps({
            "success": True,
            "order": order
        })

    return get_order


# ============================================================
# TOOL 2: POLICY SEARCH
# ============================================================

@tool
def search_policy(query: str) -> str:
    """
    Search Trendly's policy document.

    The policy document is the only source of truth for
    shipping, returns, refunds, exchanges and related policies.
    """

    if not query or not query.strip():
        return json.dumps({
            "success": False,
            "error": "EMPTY_QUERY",
            "message": "Policy search query cannot be empty."
        })

    policy = _load_policy()

    # Split policy into useful sections.
    sections = []
    current_title = "General Policy"
    current_lines = []

    for line in policy.splitlines():

        if line.startswith("#"):
            if current_lines:
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_lines).strip()
                })

            current_title = line.lstrip("#").strip()
            current_lines = []

        else:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_lines).strip()
        })

    # Simple lexical retrieval.
    query_tokens = {
        token.lower().strip(".,!?():;\"'")
        for token in query.split()
        if len(token.strip()) > 2
    }

    scored_sections = []

    for section in sections:

        section_text = (
            section["title"] + " " + section["content"]
        ).lower()

        section_tokens = {
            token.strip(".,!?():;\"'")
            for token in section_text.split()
            if len(token.strip()) > 2
        }

        score = len(
            query_tokens.intersection(section_tokens)
        )

        if score > 0:
            scored_sections.append(
                (score, section)
            )

    scored_sections.sort(
        key=lambda item: item[0],
        reverse=True
    )

    if not scored_sections:
        return json.dumps({
            "success": False,
            "error": "POLICY_NOT_FOUND",
            "message": (
                "The provided Trendly policy does not contain "
                "information answering this question."
            )
        })

    # Return top relevant sections.
    results = [
        section
        for _, section in scored_sections[:3]
    ]

    return json.dumps({
        "success": True,
        "results": results
    })


# ============================================================
# TOOL 3: INITIATE RETURN
# ============================================================

def make_initiate_return_tool(customer_id: str):

    @tool
    def initiate_return(order_id: str) -> str:
        """
        Initiate a return for an authenticated customer's order.

        Validates:
        - order ownership
        - cancellation status
        - delivery status
        - return window
        - non-returnable categories
        - final-sale restrictions
        - lost parcel handling
        """

        order = _find_order(order_id)

        if order is None:
            return json.dumps({
                "success": False,
                "error": "ORDER_NOT_FOUND",
                "message": f"No order was found with ID {order_id}."
            })

        # SECURITY
        if not _order_belongs_to_customer(order, customer_id):
            return json.dumps({
                "success": False,
                "error": "ORDER_ACCESS_DENIED",
                "message": (
                    "This order does not belong to the authenticated "
                    "customer."
                )
            })

        status = str(
            order.get("status", "")
        ).lower()

        # Cancelled orders cannot be returned.
        if status == "cancelled":
            return json.dumps({
                "success": False,
                "error": "ORDER_CANCELLED",
                "message": (
                    "Cancelled orders cannot be returned because "
                    "the purchase is no longer active."
                )
            })

        # Lost parcel is not a return.
        if status == "lost_in_transit":
            return json.dumps({
                "success": False,
                "error": "LOST_PARCEL",
                "message": (
                    "Lost parcels are handled by human support and "
                    "cannot be processed as normal returns."
                )
            })

        # Must be delivered before return.
        if status not in {
            "delivered",
            "partially_delivered"
        }:
            return json.dumps({
                "success": False,
                "error": "NOT_DELIVERED",
                "message": (
                    "The order must be delivered before a return "
                    "can be initiated."
                )
            })

        # 30-day return window.
        days = _days_since_delivery(order)

        if days is None:
            return json.dumps({
                "success": False,
                "error": "DELIVERY_DATE_UNAVAILABLE",
                "message": (
                    "The delivery date is unavailable, so return "
                    "eligibility cannot be safely determined."
                )
            })

        if days > 30:
            return json.dumps({
                "success": False,
                "error": "RETURN_WINDOW_EXPIRED",
                "message": (
                    "The 30-calendar-day return window has expired."
                ),
                "days_since_delivery": days
            })

        items = _get_items(order)

        if not items:
            return json.dumps({
                "success": False,
                "error": "NO_ITEMS",
                "message": (
                    "No returnable items were found in this order."
                )
            })

        # Check item restrictions.
        non_returnable_items = []

        for item in items:

            if _has_non_returnable_category(item):
                non_returnable_items.append(
                    item.get("name", "Unknown item")
                )

            elif _is_final_sale(item):
                non_returnable_items.append(
                    item.get("name", "Unknown item")
                )

        if non_returnable_items:
            return json.dumps({
                "success": False,
                "error": "NON_RETURNABLE",
                "items": non_returnable_items,
                "message": (
                    "One or more items in this order are not "
                    "eligible for a normal return."
                )
            })

        # Successful action.
        return_id = (
            f"RET-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )

        return json.dumps({
            "success": True,
            "action": "return_initiated",
            "return_id": return_id,
            "order_id": order_id,
            "message": (
                "Return successfully initiated. "
                "The customer can schedule a reverse pickup."
            )
        })

    return initiate_return


# ============================================================
# TOOL 4: INITIATE EXCHANGE
# ============================================================

def make_initiate_exchange_tool(customer_id: str):

    @tool
    def initiate_exchange(
        order_id: str,
        requested_size: str
    ) -> str:
        """
        Initiate a size exchange.

        Exchanges are only for different sizes.
        Final-sale items may be exchanged for size when permitted
        by the policy.

        A second exchange requires human approval.
        """

        order = _find_order(order_id)

        if order is None:
            return json.dumps({
                "success": False,
                "error": "ORDER_NOT_FOUND",
                "message": f"No order was found with ID {order_id}."
            })

        # SECURITY
        if not _order_belongs_to_customer(order, customer_id):
            return json.dumps({
                "success": False,
                "error": "ORDER_ACCESS_DENIED",
                "message": (
                    "This order does not belong to the authenticated "
                    "customer."
                )
            })

        status = str(
            order.get("status", "")
        ).lower()

        if status == "cancelled":
            return json.dumps({
                "success": False,
                "error": "ORDER_CANCELLED",
                "message": (
                    "Cancelled orders cannot be exchanged."
                )
            })

        if status == "lost_in_transit":
            return json.dumps({
                "success": False,
                "error": "LOST_PARCEL",
                "message": (
                    "Lost parcels require human support."
                )
            })

        if status not in {
            "delivered",
            "partially_delivered"
        }:
            return json.dumps({
                "success": False,
                "error": "NOT_DELIVERED",
                "message": (
                    "The order must be delivered before an "
                    "exchange can be requested."
                )
            })

        days = _days_since_delivery(order)

        if days is None:
            return json.dumps({
                "success": False,
                "error": "DELIVERY_DATE_UNAVAILABLE",
                "message": (
                    "The delivery date is unavailable, so exchange "
                    "eligibility cannot be safely determined."
                )
            })

        if days > 30:
            return json.dumps({
                "success": False,
                "error": "EXCHANGE_WINDOW_EXPIRED",
                "message": (
                    "The 30-calendar-day exchange window has expired."
                ),
                "days_since_delivery": days
            })

        items = _get_items(order)

        if not items:
            return json.dumps({
                "success": False,
                "error": "NO_ITEMS",
                "message": (
                    "No exchangeable items were found in this order."
                )
            })

        # Jewellery cannot be exchanged.
        exchangeable_items = [
            item
            for item in items
            if not _is_jewellery(item)
        ]

        if not exchangeable_items:
            return json.dumps({
                "success": False,
                "error": "NON_EXCHANGEABLE",
                "message": (
                    "No exchangeable item was found in this order."
                )
            })

        # Exchange is only for size.
        if not requested_size or not requested_size.strip():
            return json.dumps({
                "success": False,
                "error": "SIZE_REQUIRED",
                "message": (
                    "A requested size is required for an exchange."
                )
            })

        # One exchange per order/item for this prototype.
        exchange_key = order_id.upper()

        if exchange_key in EXCHANGE_HISTORY:
            return json.dumps({
                "success": False,
                "error": "SECOND_EXCHANGE",
                "message": (
                    "This item has already been exchanged once. "
                    "A second exchange requires human approval."
                )
            })

        # Final-sale items are allowed only for size exchange.
        final_sale_items = [
            item
            for item in exchangeable_items
            if _is_final_sale(item)
        ]

        # Record successful exchange request.
        EXCHANGE_HISTORY.add(exchange_key)

        return json.dumps({
            "success": True,
            "action": "exchange_requested",
            "order_id": order_id,
            "requested_size": requested_size,
            "final_sale_item": bool(final_sale_items),
            "message": (
                "Size exchange request created successfully."
            )
        })

    return initiate_exchange


# ============================================================
# TOOL 5: CREATE STORE CREDIT
# ============================================================

def make_create_store_credit_tool(customer_id: str):

    @tool
    def create_store_credit(
        order_id: str,
        amount: int,
        reason: str
    ) -> str:
        """
        Create policy-authorized store credit.

        Currently supports the ₹250 credit for qualifying delayed
        deliveries.
        """

        order = _find_order(order_id)

        if order is None:
            return json.dumps({
                "success": False,
                "error": "ORDER_NOT_FOUND",
                "message": f"No order was found with ID {order_id}."
            })

        if not _order_belongs_to_customer(order, customer_id):
            return json.dumps({
                "success": False,
                "error": "ORDER_ACCESS_DENIED",
                "message": (
                    "This order does not belong to the authenticated "
                    "customer."
                )
            })

        if reason != "delayed_delivery":
            return json.dumps({
                "success": False,
                "error": "UNAUTHORIZED_CREDIT",
                "message": (
                    "Store credit cannot be created for this reason."
                )
            })

        if amount != 250:
            return json.dumps({
                "success": False,
                "error": "INVALID_CREDIT_AMOUNT",
                "message": (
                    "Only the policy-authorized ₹250 delayed-delivery "
                    "credit can be created."
                )
            })

        # Validate delayed-delivery eligibility.
        estimated = _parse_date(
            order.get("estimated_delivery")
        )

        if estimated is None:
            return json.dumps({
                "success": False,
                "error": "ESTIMATED_DATE_UNAVAILABLE",
                "message": (
                    "The estimated delivery date is unavailable."
                )
            })

        days_late = (
            CURRENT_DATE - estimated
        ).days

        # Policy requirement:
        # more than 3 business days late.
        #
        # We deliberately don't attempt complex business-day
        # calculations here unless the policy/order data requires it.
        if days_late <= 3:
            return json.dumps({
                "success": False,
                "error": "NOT_ELIGIBLE",
                "message": (
                    "This order does not currently meet the "
                    "delay threshold for the policy credit."
                )
            })

        credit_id = (
            f"CR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )

        return json.dumps({
            "success": True,
            "action": "store_credit_created",
            "credit_id": credit_id,
            "order_id": order_id,
            "amount": amount,
            "message": (
                "₹250 store credit created successfully."
            )
        })

    return create_store_credit


# ============================================================
# TOOL 6: DAMAGED ITEM
# ============================================================

def make_handle_damaged_item_tool(customer_id: str):

    @tool
    def handle_damaged_item(
        order_id: str,
        resolution: str = "pending"
    ) -> str:
        """
        Handle a damaged, defective, or incorrect item request.

        The policy requires the issue to be reported within
        48 hours of delivery and requires a photo.
        """

        order = _find_order(order_id)

        if order is None:
            return json.dumps({
                "success": False,
                "error": "ORDER_NOT_FOUND",
                "message": f"No order was found with ID {order_id}."
            })

        if not _order_belongs_to_customer(order, customer_id):
            return json.dumps({
                "success": False,
                "error": "ORDER_ACCESS_DENIED",
                "message": (
                    "This order does not belong to the authenticated "
                    "customer."
                )
            })

        status = str(
            order.get("status", "")
        ).lower()

        if status != "delivered":
            return json.dumps({
                "success": False,
                "error": "NOT_DELIVERED",
                "message": (
                    "A damaged-item claim requires a delivered order."
                )
            })

        days = _days_since_delivery(order)

        if days is None:
            return json.dumps({
                "success": False,
                "error": "DELIVERY_DATE_UNAVAILABLE",
                "message": (
                    "The delivery date is unavailable."
                )
            })

        # 48 hours = 2 calendar days for this simple prototype.
        if days > 2:
            return json.dumps({
                "success": False,
                "error": "DAMAGE_REPORT_WINDOW_EXPIRED",
                "message": (
                    "Damaged or incorrect items must be reported "
                    "within 48 hours of delivery."
                )
            })

        if resolution not in {
            "replacement",
            "refund",
            "pending"
        }:
            return json.dumps({
                "success": False,
                "error": "INVALID_RESOLUTION",
                "message": (
                    "Resolution must be replacement, refund, "
                    "or pending."
                )
            })

        claim_id = (
            f"DAM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )

        return json.dumps({
            "success": True,
            "action": "damaged_item_claim_created",
            "claim_id": claim_id,
            "order_id": order_id,
            "resolution": resolution,
            "message": (
                "Damaged-item claim created successfully."
            )
        })

    return handle_damaged_item


# ============================================================
# TOOL 7: HUMAN ESCALATION
# ============================================================

@tool
def escalate_to_human(
    reason: str,
    summary: str,
    order_id: str = ""
) -> str:
    """
    Escalate a customer issue to a human support agent.

    Use this when policy requires human handling, the assistant
    lacks enough information, the request is outside the supported
    workflow, or a safety/privacy restriction applies.
    """

    escalation_id = (
        f"ESC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )

    return json.dumps({
        "success": True,
        "escalation_id": escalation_id,
        "status": "escalated",
        "order_id": order_id or None,
        "reason": reason,
        "summary": summary,
        "message": (
            "The issue has been escalated to a human support agent."
        )
    })


# ============================================================
# BUILD TOOLS FOR AUTHENTICATED CUSTOMER
# ============================================================

def get_tools(customer_id: str):
    """
    Return all tools available to an authenticated customer.

    customer_id is application-controlled context and is never
    taken from the user's natural-language message.
    """

    return [
        make_get_order_tool(customer_id),
        search_policy,
        make_initiate_return_tool(customer_id),
        make_initiate_exchange_tool(customer_id),
        make_create_store_credit_tool(customer_id),
        make_handle_damaged_item_tool(customer_id),
        escalate_to_human,
    ]