import json

import pytest

from app.tools import (
    _get_order,
    make_get_order_tool,
    make_initiate_exchange_tool,
    make_initiate_return_tool,
    search_policy,
    escalate_to_human,
)

# ORDER LOOKUP TESTS

def test_order_lookup_success():

    tool = make_get_order_tool("C-101")

    result = tool.invoke({
        "order_id": "TR-4522"
    })

    data = json.loads(result)

    assert data["success"] is True
    assert data["order"]["order_id"] == "TR-4522"
    assert data["order"]["status"] == "delivered"


def test_order_not_found():

    tool = make_get_order_tool("C-101")

    result = tool.invoke({
        "order_id": "TR-9999"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "ORDER_NOT_FOUND"


def test_other_customer_order_is_blocked():


    tool = make_get_order_tool("C-100")

    result = tool.invoke({
        "order_id": "TR-4522"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "ORDER_ACCESS_DENIED"


# POLICY TESTS

def test_policy_return_window():

    result = search_policy.invoke({
        "query": "return window 30 days"
    })

    data = json.loads(result)

    assert data["success"] is True

    text = " ".join(data["results"]).lower()

    assert "30 calendar days" in text


def test_policy_final_sale():

    result = search_policy.invoke({
        "query": "final sale refund exchange"
    })

    data = json.loads(result)

    assert data["success"] is True

    text = " ".join(data["results"]).lower()

    assert "size exchange only" in text


def test_policy_lost_parcel():

    result = search_policy.invoke({
        "query": "lost parcel human refund replacement"
    })

    data = json.loads(result)

    assert data["success"] is True

    text = " ".join(data["results"]).lower()

    assert "lost-parcel claim" in text


# RETURN TESTS

def test_happy_path_return():

    # TR-4530 belongs to C-101.
    tool = make_initiate_return_tool("C-101")

    result = tool.invoke({
        "order_id": "TR-4530"
    })

    data = json.loads(result)

    assert data["success"] is True
    assert data["action"] == "return_initiated"


def test_old_order_return_rejected():

    # TR-4523 is outside the 30-day window.
    tool = make_initiate_return_tool("C-102")

    result = tool.invoke({
        "order_id": "TR-4523"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "RETURN_WINDOW_EXPIRED"


def test_jewellery_return_rejected():

    # TR-4527 is within 30 days but jewellery is non-returnable.
    tool = make_initiate_return_tool("C-102")

    result = tool.invoke({
        "order_id": "TR-4527"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "NON_RETURNABLE_CATEGORY"


def test_final_sale_refund_rejected():

    # TR-4528 is final sale.
    tool = make_initiate_return_tool("C-103")

    result = tool.invoke({
        "order_id": "TR-4528"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "FINAL_SALE"


def test_cancelled_order_return_rejected():

    # TR-4529 is already cancelled and refunded.
    tool = make_initiate_return_tool("C-100")

    result = tool.invoke({
        "order_id": "TR-4529"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "ORDER_CANCELLED"


# LOST PARCEL TEST

def test_lost_parcel_is_not_return():

    # TR-4526 belongs to C-101.
    tool = make_initiate_return_tool("C-101")

    result = tool.invoke({
        "order_id": "TR-4526"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "LOST_PARCEL"


# EXCHANGE TESTS

def test_final_sale_size_exchange_allowed():

    # TR-4528 is final sale.
    # Final sale still permits SIZE exchange.
    tool = make_initiate_exchange_tool("C-103")

    result = tool.invoke({
        "order_id": "TR-4528",
        "requested_size": "L"
    })

    data = json.loads(result)

    assert data["success"] is True
    assert data["action"] == "exchange_requested"
    assert data["requested_size"] == "L"


def test_cancelled_order_exchange_rejected():

    tool = make_initiate_exchange_tool("C-100")

    result = tool.invoke({
        "order_id": "TR-4529",
        "requested_size": "L"
    })

    data = json.loads(result)

    assert data["success"] is False
    assert data["error"] == "ORDER_CANCELLED"


# ESCALATION TEST

def test_human_escalation():

    result = escalate_to_human.invoke({
        "reason": "Lost parcel",
        "summary": (
            "Customer reports that order TR-4526 has been lost "
            "in transit and requests a refund."
        ),
        "order_id": "TR-4526",
    })

    data = json.loads(result)

    assert data["success"] is True
    assert data["status"] == "escalated"
    assert data["order_id"] == "TR-4526"
    assert data["reason"] == "Lost parcel"