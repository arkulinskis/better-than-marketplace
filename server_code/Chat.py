"""Chats between a buyer and a seller, one per item and buyer.

Only the two people in a chat can read it. Emails are never shared: people see each other's display names.
The chat page polls (poll_chat) every few seconds while it's open; the tab bar polls badges() for unread counts.
"""
import re

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables
import anvil.tables.query as q

from . import common as C
from . import Market

MAX_TEXT = 1000


def _role(c, me):
    if c["buyer"] == me:
        return "buying"
    if c["seller"] == me:
        return "selling"
    return None


def _chat(key, me):
    if not isinstance(key, str) or not key:
        return None, C.fail("That chat doesn't exist.")
    c = app_tables.chats.get(key=key)
    if c is None or _role(c, me) is None:
        return None, C.fail("That chat doesn't exist.")
    return c, None


def _kind(m):
    """"" for a person's message, "auto" for the still-available auto-answer (messages.kind is a 2026-11-20 column:
    read through a guard until the user accepts the schema change)."""
    try:
        return m["kind"] or ""
    except Exception:
        return ""


def _msg(m, me):
    return {"id": m.get_id(), "text": m["text"], "at": C.iso(m["created"]), "mine": m["sender"] == me and m["sender"] is not None,
            "kind": _kind(m)}


AVAILABLE = re.compile(r"\b(still\s+)?(available|for sale|dispo(nible)?)\b", re.I)


def _ago(when):
    days = (C.now() - when).days if when else 0
    return "today" if days < 1 else "yesterday" if days < 2 else "%d days ago" % days


def _auto_answer(c, r, text):
    """A new chat that opens with "Is this still available?" gets an instant answer from the item's live status, so
    the buyer isn't left waiting and the seller doesn't have to type "yes" for the hundredth time."""
    if len(text) > 120 or not AVAILABLE.search(text):
        return
    first = (C.name_of(r["owner"]) or "the seller").split(" ")[0]
    if r["status"] == "reserved":
        answer = "Auto-answer: it's reserved for someone right now. Ask %s if you can be next in line." % first
    else:
        answer = ("Auto-answer: yes, it's still for sale (listed %s). Ask %s about a time to pick it up."
                  % (_ago(r["created"]), first))
    try:
        app_tables.messages.add_row(chat=c, sender=None, text=answer, created=C.now(), is_demo=False, kind="auto")
    except Exception:
        pass  # the kind column isn't there yet: no auto-answer


def _add(c, me, text):
    now = C.now()
    m = app_tables.messages.add_row(chat=c, sender=me, text=text, created=now, is_demo=False)
    other = "seller_unread" if c["buyer"] == me else "buyer_unread"
    c.update(last_at=now, last_text=text[:140], last_sender=me, **{other: (c[other] or 0) + 1})
    return m


def _clean(text):
    text = C.text(text, MAX_TEXT, multiline=True)
    if not text:
        return None, C.fail("Write a message first.")
    if C.rate_limited("message", 60, 600):
        return None, C.fail("You're sending messages very fast. Wait a minute and try again.")
    return text, None


@anvil.server.callable(require_user=True)
def start_chat(listing_key, text):
    """Message the seller about an item (or add to the chat you already have about it)."""
    me = C.require_adult()
    r = Market.listing_by_key(listing_key)
    if not Market.can_see(r, me) or r["status"] == "sold":
        return C.fail("This item isn't available any more.")
    if r["owner"] == me:
        return C.fail("That's your own item.")
    if r["owner"]["enabled"] is False and not r["owner"]["is_demo"]:
        return C.fail("This seller isn't taking messages.")
    text, problem = _clean(text)
    if problem:
        return problem
    c = app_tables.chats.get(listing=r, buyer=me)
    new = c is None
    if c is None:
        c = app_tables.chats.add_row(key=C.token(12), listing=r, title=r["title"], buyer=me, seller=r["owner"],
                                     created=C.now(), buyer_unread=0, seller_unread=0, is_demo=False)
    _add(c, me, text)
    if new:
        _auto_answer(c, r, text)
    return C.ok(chat=c["key"])


def _summary(c, me):
    r = c["listing"]
    role = _role(c, me)
    other = c["seller"] if role == "buying" else c["buyer"]
    keys = (r["photo_keys"] or []) if r is not None else []
    return {"key": c["key"], "title": c["title"], "role": role, "other": C.name_of(other),
            "other_key": C.public_key(other) if other is not None else None,
            "cover": keys[0] if keys else None, "listing": r["key"] if r is not None else None,
            "status": r["status"] if r is not None else "gone", "price": r["price"] if r is not None else None,
            "price_mode": r["price_mode"] if r is not None else None, "last_text": c["last_text"] or "",
            "last_mine": c["last_sender"] == me, "last_at": C.iso(c["last_at"] or c["created"]),
            "unread": (c["buyer_unread"] if role == "buying" else c["seller_unread"]) or 0,
            # the item's area (~1 km, like its map circle): where "Find a safe spot" looks around
            "spot": {"lat": round(r["lat"], 2), "lng": round(r["lng"], 2)} if r is not None and r["lat"] is not None else None}


@anvil.server.callable(require_user=True)
def list_chats():
    me = C.require_user()
    rows = list(app_tables.chats.search(q.any_of(buyer=me, seller=me)))
    rows.sort(key=lambda c: c["last_at"] or c["created"], reverse=True)
    return {"chats": [_summary(c, me) for c in rows[:200]]}


def _mark_read(c, me):
    col = "buyer_unread" if c["buyer"] == me else "seller_unread"
    if c[col]:
        c[col] = 0


@anvil.server.callable(require_user=True)
def get_chat(key):
    me = C.require_user()
    c, problem = _chat(key, me)
    if problem:
        return problem
    _mark_read(c, me)
    msgs = list(app_tables.messages.search(tables.order_by("created"), chat=c))[-300:]
    from . import Pickup
    return C.ok(chat=_summary(c, me), messages=[_msg(m, me) for m in msgs], plan=Pickup.plan_dict(c, me))


@anvil.server.callable(require_user=True)
def send_message(key, text):
    me = C.require_adult()
    c, problem = _chat(key, me)
    if problem:
        return problem
    other = c["seller"] if c["buyer"] == me else c["buyer"]
    if other is None or (other["enabled"] is False and not other["is_demo"]):
        return C.fail("This person isn't taking messages.")
    text, problem = _clean(text)
    if problem:
        return problem
    m = _add(c, me, text)
    return C.ok(message=_msg(m, me))


@anvil.server.callable(require_user=True)
def poll_chat(key, after=None):
    """Messages from `after` on (the time of the newest message the page has). Inclusive, because two messages
    can share a timestamp: the page drops the ones it already shows (by id)."""
    me = C.require_user()
    c, problem = _chat(key, me)
    if problem:
        return problem
    msgs = app_tables.messages.search(tables.order_by("created"), chat=c)
    if isinstance(after, str) and after:
        msgs = [m for m in msgs if C.iso(m["created"]) >= after]
    _mark_read(c, me)
    from . import Pickup
    return C.ok(messages=[_msg(m, me) for m in list(msgs)[-100:]], plan=Pickup.plan_dict(c, me))


@anvil.server.callable(require_user=True)
def badges():
    """Unread messages, for the tab bar."""
    me = C.require_user()
    n = sum((c["buyer_unread"] or 0) for c in app_tables.chats.search(buyer=me)) + \
        sum((c["seller_unread"] or 0) for c in app_tables.chats.search(seller=me))
    return {"unread": n}
