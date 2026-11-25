"""JSON-file persistence for billing entities (matches AuthStore style)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from app.billing.store_models import (
    BillingEventRecord,
    CustomerMap,
    InvoiceRecord,
    PaymentRecord,
    SubscriptionRecord,
    UsageCounters,
)


class BillingStore:
    """Thread-safe JSON store for subscriptions, payments, invoices, events."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._subscriptions: dict[str, SubscriptionRecord] = {}
        self._by_user: dict[str, str] = {}
        self._by_provider_sub: dict[str, str] = {}
        self._payments: dict[str, PaymentRecord] = {}
        self._by_provider_payment: dict[str, str] = {}
        self._invoices: dict[str, InvoiceRecord] = {}
        self._by_provider_invoice: dict[str, str] = {}
        self._events: dict[str, BillingEventRecord] = {}
        self._by_provider_event: dict[str, str] = {}
        self._usage: dict[str, UsageCounters] = {}
        self._customers: dict[str, CustomerMap] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # Do not silently discard subscriptions, invoices or webhook
            # idempotency records when the durable billing file is damaged.
            raise RuntimeError(
                f"Cannot load NEXA billing store at {self._path}: {exc}"
            ) from exc
        for entry in raw.get("subscriptions", []):
            item = SubscriptionRecord.model_validate(entry)
            self._index_subscription(item)
        for entry in raw.get("payments", []):
            item = PaymentRecord.model_validate(entry)
            self._payments[item.id] = item
            self._by_provider_payment[item.provider_payment_id] = item.id
        for entry in raw.get("invoices", []):
            item = InvoiceRecord.model_validate(entry)
            self._invoices[item.id] = item
            self._by_provider_invoice[item.provider_invoice_id] = item.id
        for entry in raw.get("events", []):
            item = BillingEventRecord.model_validate(entry)
            self._events[item.id] = item
            self._by_provider_event[item.provider_event_id] = item.id
        for entry in raw.get("usage", []):
            item = UsageCounters.model_validate(entry)
            self._usage[f"{item.user_id}:{item.period_key}"] = item
        for entry in raw.get("customers", []):
            item = CustomerMap.model_validate(entry)
            self._customers[item.user_id] = item

    def _index_subscription(self, item: SubscriptionRecord) -> None:
        self._subscriptions[item.id] = item
        self._by_user[item.user_id] = item.id
        if item.provider_subscription_id:
            self._by_provider_sub[item.provider_subscription_id] = item.id

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "subscriptions": [s.model_dump(mode="json") for s in self._subscriptions.values()],
            "payments": [p.model_dump(mode="json") for p in self._payments.values()],
            "invoices": [i.model_dump(mode="json") for i in self._invoices.values()],
            "events": [e.model_dump(mode="json") for e in self._events.values()],
            "usage": [u.model_dump(mode="json") for u in self._usage.values()],
            "customers": [c.model_dump(mode="json") for c in self._customers.values()],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    # --- subscriptions ----------------------------------------------------
    def save_subscription(self, sub: SubscriptionRecord) -> SubscriptionRecord:
        with self._lock:
            # drop stale provider index if id changed
            old = self._subscriptions.get(sub.id)
            if old and old.provider_subscription_id and old.provider_subscription_id != sub.provider_subscription_id:
                self._by_provider_sub.pop(old.provider_subscription_id, None)
            self._index_subscription(sub)
            self._flush()
        return sub

    def get_subscription(self, subscription_id: str) -> SubscriptionRecord | None:
        with self._lock:
            return self._subscriptions.get(subscription_id)

    def get_subscription_for_user(self, user_id: str) -> SubscriptionRecord | None:
        with self._lock:
            sid = self._by_user.get(user_id)
            return self._subscriptions.get(sid) if sid else None

    def get_subscription_by_provider_id(self, provider_subscription_id: str) -> SubscriptionRecord | None:
        with self._lock:
            sid = self._by_provider_sub.get(provider_subscription_id)
            return self._subscriptions.get(sid) if sid else None

    def delete_user_data(self, user_id: str) -> int:
        """Remove local billing records for an account after provider cancellation."""
        with self._lock:
            subscription_ids = {
                sid for sid, item in self._subscriptions.items() if item.user_id == user_id
            }
            provider_subscription_ids = {
                item.provider_subscription_id
                for item in self._subscriptions.values()
                if item.user_id == user_id and item.provider_subscription_id
            }
            payment_ids = {pid for pid, item in self._payments.items() if item.user_id == user_id}
            invoice_ids = {iid for iid, item in self._invoices.items() if item.user_id == user_id}
            removed = (
                len(subscription_ids)
                + len(payment_ids)
                + len(invoice_ids)
                + int(user_id in self._customers)
                + sum(1 for item in self._usage.values() if item.user_id == user_id)
            )
            for sid in subscription_ids:
                self._subscriptions.pop(sid, None)
            for provider_id in provider_subscription_ids:
                self._by_provider_sub.pop(provider_id, None)
            self._by_user.pop(user_id, None)
            for pid in payment_ids:
                item = self._payments.pop(pid, None)
                if item:
                    self._by_provider_payment.pop(item.provider_payment_id, None)
            for iid in invoice_ids:
                item = self._invoices.pop(iid, None)
                if item:
                    self._by_provider_invoice.pop(item.provider_invoice_id, None)
            self._usage = {
                key: item for key, item in self._usage.items() if item.user_id != user_id
            }
            self._customers.pop(user_id, None)
            self._flush()
            return removed

    # --- payments ---------------------------------------------------------
    def save_payment(self, payment: PaymentRecord) -> PaymentRecord:
        with self._lock:
            self._payments[payment.id] = payment
            self._by_provider_payment[payment.provider_payment_id] = payment.id
            self._flush()
        return payment

    def get_payment_by_provider_id(self, provider_payment_id: str) -> PaymentRecord | None:
        with self._lock:
            pid = self._by_provider_payment.get(provider_payment_id)
            return self._payments.get(pid) if pid else None

    def list_payments_for_user(self, user_id: str) -> list[PaymentRecord]:
        with self._lock:
            items = [p for p in self._payments.values() if p.user_id == user_id]
            return sorted(items, key=lambda p: p.created_at, reverse=True)

    # --- invoices ---------------------------------------------------------
    def save_invoice(self, invoice: InvoiceRecord) -> InvoiceRecord:
        with self._lock:
            self._invoices[invoice.id] = invoice
            self._by_provider_invoice[invoice.provider_invoice_id] = invoice.id
            self._flush()
        return invoice

    def get_invoice_by_provider_id(self, provider_invoice_id: str) -> InvoiceRecord | None:
        with self._lock:
            iid = self._by_provider_invoice.get(provider_invoice_id)
            return self._invoices.get(iid) if iid else None

    def list_invoices_for_user(self, user_id: str) -> list[InvoiceRecord]:
        with self._lock:
            items = [i for i in self._invoices.values() if i.user_id == user_id]
            return sorted(items, key=lambda i: i.created_at, reverse=True)

    # --- events (idempotency) ---------------------------------------------
    def get_event_by_provider_id(self, provider_event_id: str) -> BillingEventRecord | None:
        with self._lock:
            eid = self._by_provider_event.get(provider_event_id)
            return self._events.get(eid) if eid else None

    def save_event(self, event: BillingEventRecord) -> BillingEventRecord:
        with self._lock:
            self._events[event.id] = event
            self._by_provider_event[event.provider_event_id] = event.id
            self._flush()
        return event

    # --- usage ------------------------------------------------------------
    def get_usage(self, user_id: str, period_key: str) -> UsageCounters | None:
        with self._lock:
            return self._usage.get(f"{user_id}:{period_key}")

    def save_usage(self, usage: UsageCounters) -> UsageCounters:
        with self._lock:
            self._usage[f"{usage.user_id}:{usage.period_key}"] = usage
            self._flush()
        return usage

    # --- customers --------------------------------------------------------
    def get_customer(self, user_id: str) -> CustomerMap | None:
        with self._lock:
            return self._customers.get(user_id)

    def save_customer(self, customer: CustomerMap) -> CustomerMap:
        with self._lock:
            self._customers[customer.user_id] = customer
            self._flush()
        return customer

    def get_user_id_by_customer(self, provider_customer_id: str) -> str | None:
        with self._lock:
            for c in self._customers.values():
                if c.provider_customer_id == provider_customer_id:
                    return c.user_id
        return None
