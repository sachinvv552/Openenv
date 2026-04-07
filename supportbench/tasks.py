"""Deterministic task fixtures for the SupportBench environment."""

from __future__ import annotations

from typing import Dict, List


SUPPORT_POLICIES = [
    "Refunds are allowed within 30 days for duplicate charges or accidental renewals.",
    "Security-sensitive account changes must be escalated to Trust & Safety.",
    "Enterprise or VIP customers must receive high priority routing.",
    "Shipping delays over 7 days require a proactive apology and replacement offer.",
    "Agents should avoid requesting information that is already present in the ticket.",
]


TASKS: List[Dict] = [
    {
        "task_id": "easy_duplicate_charge",
        "difficulty": "easy",
        "title": "Resolve a duplicate subscription charge",
        "customer_tier": "standard",
        "ticket": {
            "ticket_id": "TCK-1001",
            "customer_name": "Maya Patel",
            "channel": "email",
            "subject": "Charged twice for April plan",
            "message": (
                "Hi team, I renewed my Starter plan yesterday and my card was charged twice "
                "within a minute. I only intended to pay once. Can you reverse the extra charge?"
            ),
            "metadata": {
                "plan": "Starter",
                "country": "IN",
                "days_since_charge": 1,
                "duplicate_charge_count": 2,
                "previous_tickets": 0,
            },
        },
        "expected": {
            "category": "billing",
            "priority": "medium",
            "queue": "billing_ops",
            "escalate": False,
            "resolution": "refund_duplicate",
            "reply_template": "refund_confirmed",
            "must_mention": ["duplicate charge", "refund", "3-5 business days"],
        },
        "grader_weights": {
            "classify": 0.30,
            "assign": 0.20,
            "reply": 0.20,
            "resolve": 0.30,
        },
        "max_steps": 6,
    },
    {
        "task_id": "medium_shipping_delay",
        "difficulty": "medium",
        "title": "Handle a delayed replacement shipment",
        "customer_tier": "pro",
        "ticket": {
            "ticket_id": "TCK-2004",
            "customer_name": "Jordan Lee",
            "channel": "chat",
            "subject": "Replacement order hasn't moved in 10 days",
            "message": (
                "My replacement keyboard was marked shipped 10 days ago but the tracking page "
                "still says label created. I need it before next week. Can someone help?"
            ),
            "metadata": {
                "tracking_status": "label_created",
                "days_in_transit": 10,
                "replacement_order": True,
                "previous_tickets": 1,
                "country": "US",
            },
        },
        "expected": {
            "category": "shipping",
            "priority": "high",
            "queue": "logistics",
            "escalate": False,
            "resolution": "replacement_reship",
            "reply_template": "shipping_apology",
            "must_mention": ["delay", "replacement", "priority shipping"],
        },
        "grader_weights": {
            "classify": 0.25,
            "assign": 0.20,
            "reply": 0.25,
            "resolve": 0.30,
        },
        "max_steps": 7,
    },
    {
        "task_id": "hard_account_takeover",
        "difficulty": "hard",
        "title": "Triage a likely account takeover for a VIP customer",
        "customer_tier": "vip",
        "ticket": {
            "ticket_id": "TCK-3059",
            "customer_name": "Elena Garcia",
            "channel": "email",
            "subject": "Urgent: email changed and invoices are missing",
            "message": (
                "I logged in this morning and my recovery email was changed to an address I don't "
                "recognize. Two invoices are gone and my team cannot access the workspace. "
                "Please lock this down immediately."
            ),
            "metadata": {
                "workspace_size": 43,
                "recent_email_change": True,
                "missing_invoices": 2,
                "previous_tickets": 2,
                "country": "ES",
            },
        },
        "expected": {
            "category": "security",
            "priority": "urgent",
            "queue": "trust_safety",
            "escalate": True,
            "resolution": "account_lock_and_escalate",
            "reply_template": "security_escalation",
            "must_mention": ["secure", "specialist", "temporarily lock"],
        },
        "grader_weights": {
            "classify": 0.20,
            "assign": 0.25,
            "reply": 0.20,
            "resolve": 0.35,
        },
        "max_steps": 8,
    },
]


TASK_INDEX = {task["task_id"]: task for task in TASKS}


REPLY_TEMPLATES = {
    "refund_confirmed": (
        "I'm sorry about the duplicate charge. I've processed a refund for the extra payment. "
        "You should see the funds return in 3-5 business days."
    ),
    "shipping_apology": (
        "I'm sorry your replacement has been delayed. I'm arranging a new shipment with priority "
        "shipping and will share updated tracking as soon as it is created."
    ),
    "security_escalation": (
        "I'm sorry you're dealing with this. I've temporarily locked the account and escalated "
        "your case to a security specialist for immediate review."
    ),
}
