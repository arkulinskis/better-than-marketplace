"""Pickup plans inside a chat, and each member's pickup record (2026-11-20).

One side proposes a time and a public place; the other confirms (or suggests another). On the day either side can
say "On my way", "Running late" or "Can't make it" (each posts a normal chat line). From 15 minutes before the time,
each side marks how it went once: "met" or "noshow". A member's record = the pickups the OTHER side marked, and how
many of those they showed up to ("Showed up to 7 of 7 pickups" on their seller page and items).

Table `meetups` is new: every read goes through a guard so the live app keeps working until the user accepts the
schema change (no plan shown, no record).
"""
import datetime as dt

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Chat

MARK_EARLY = dt.timedelta(minutes=15)   # marking opens this long before the agreed time
MAX_AHEAD = dt.timedelta(days=30)
ACTIONS = {
    "confirm": "✓ Confirmed. See you then!",
    "on_way": "On my way!",
    "late": "Running about 10 minutes late, sorry!",
    "cancel": "Sorry, I can't make it. Let's find another time.",
}


def _open_plan(c):
    """The chat's newest plan that isn't cancelled (or None). Raises if the table doesn't exist yet."""
    for m in app_tables.meetups.search(tables.order_by("created", ascending=False), chat=c):
        if m["status"] != "cancelled":
            return m
    return None


def _side(c, me):
    return "buyer" if c["buyer"] == me else "seller"


def plan_dict(c, me):
    """The plan card for one person in the chat, or None (no plan, or the table isn't there yet)."""
    try:
        m = _open_plan(c)
    except Exception:
        return None
    if m is None:
        return None
    side = _side(c, me)
    other = "seller" if side == "buyer" else "buyer"
    mine_mark, their_mark = m[side + "_mark"] or "", m[other + "_mark"] or ""
    can_mark = m["status"] == "confirmed" and not mine_mark and m["at"] is not None and C.now() >= m["at"] - MARK_EARLY
    return {"id": m.get_id(), "at": C.iso(m["at"]), "place": m["place"] or "", "lat": m["place_lat"], "lng": m["place_lng"],
            "status": m["status"], "mine": m["proposer"] == me, "my_mark": mine_mark, "their_mark": their_mark,
            "can_mark": can_mark, "stamp": C.iso(m["updated"] or m["created"])}


def record(u):
    """{met, total}: of the pickups the other side marked, how many this person showed up to."""
    met = total = 0
    try:
        for side, other in (("seller", "buyer_mark"), ("buyer", "seller_mark")):
            for m in app_tables.meetups.search(**{side: u}):
                if m[other] in ("met", "noshow"):
                    total += 1
                    met += m[other] == "met"
    except Exception:
        return {"met": 0, "total": 0}
    return {"met": met, "total": total}


def _chat_for(key, me):
    c, problem = Chat._chat(key, me)
    if problem:
        return None, problem
    r = c["listing"]
    if r is None or r["status"] == "sold":
        return None, C.fail("This item isn't for sale any more.")
    other = c["seller"] if c["buyer"] == me else c["buyer"]
    if other is None or (other["enabled"] is False and not other["is_demo"]):
        return None, C.fail("This person isn't taking messages.")
    return c, None


def _when(at_iso):
    try:
        at = dt.datetime.fromisoformat(str(at_iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        return None
    now = C.now()
    if at < now - dt.timedelta(minutes=10) or at > now + MAX_AHEAD:
        return None
    return at


def _reply(c, me, m=None):
    return C.ok(plan=plan_dict(c, me), message=Chat._msg(m, me) if m is not None else None)


@anvil.server.callable(require_user=True)
def propose_pickup(chat_key, at_iso, place, lat=None, lng=None, label=""):
    """Suggest a time (ISO, from the browser's clock) and a public place. `label` is the time as the proposer's
    browser writes it ("Sat 21 Nov, 2:00 pm"), used in the chat line."""
    me = C.require_adult()
    c, problem = _chat_for(chat_key, me)
    if problem:
        return problem
    at = _when(at_iso)
    if at is None:
        return C.fail("Pick a time in the next 30 days.")
    place = C.text(place, 120)
    if not place:
        return C.fail("Say where to meet: a public place is best.")
    if C.rate_limited("pickup", 30, 3600):
        return C.fail("That's a lot of plans. Wait a little and try again.")
    try:
        old = _open_plan(c)
    except Exception:
        return C.fail("Pickup plans aren't switched on yet. Agree on a time in the chat for now.")
    if old is not None and not old["buyer_mark"] and not old["seller_mark"]:
        old.update(status="cancelled", updated=C.now())
    now = C.now()
    app_tables.meetups.add_row(chat=c, buyer=c["buyer"], seller=c["seller"], proposer=me, at=at, place=place,
                               place_lat=C.coord(lat, 90), place_lng=C.coord(lng, 180), status="proposed",
                               buyer_mark="", seller_mark="", created=now, updated=now, is_demo=False)
    when = C.text(label, 60) or "the time in the plan"
    m = Chat._add(c, me, "Pickup plan: %s at %s. Does that work for you?" % (when, place))
    return _reply(c, me, m)


@anvil.server.callable(require_user=True)
def answer_pickup(chat_key, action):
    """confirm (the other side's proposal) | on_way | late (a confirmed plan) | cancel (either side)."""
    me = C.require_adult()
    if action not in ACTIONS:
        return C.fail("That doesn't work here.")
    c, problem = _chat_for(chat_key, me)
    if problem:
        return problem
    try:
        m = _open_plan(c)
    except Exception:
        m = None
    if m is None or m[_side(c, me) + "_mark"]:
        return C.fail("There's no pickup plan to answer. Plan one first.")
    if action == "confirm" and (m["status"] != "proposed" or m["proposer"] == me):
        return C.fail("Only the other person can confirm this plan.")
    if action in ("on_way", "late") and m["status"] != "confirmed":
        return C.fail("Confirm the plan first.")
    if C.rate_limited("pickup", 30, 3600):
        return C.fail("That's a lot of updates. Wait a little and try again.")
    text = ACTIONS[action]
    if action == "cancel" and m["status"] == "proposed" and m["proposer"] == me:
        text = "I took back my pickup plan. Let's find another time."
    if action == "confirm":
        m.update(status="confirmed", updated=C.now())
    elif action == "cancel":
        m.update(status="cancelled", updated=C.now())
    msg = Chat._add(c, me, text)
    return _reply(c, me, msg)


@anvil.server.callable(require_user=True)
def mark_pickup(chat_key, met):
    """How it went, once per side, from 15 minutes before the time: met=True ("We met") or False ("They didn't show")."""
    me = C.require_user()
    c, problem = Chat._chat(chat_key, me)
    if problem:
        return problem
    try:
        m = _open_plan(c)
    except Exception:
        m = None
    if m is None or m["status"] != "confirmed":
        return C.fail("There's no confirmed pickup to mark.")
    col = _side(c, me) + "_mark"
    if m[col]:
        return C.fail("You already said how it went.")
    if m["at"] is None or C.now() < m["at"] - MARK_EARLY:
        return C.fail("You can say how it went once it's time to meet.")
    m.update(**{col: "met" if met is True else "noshow", "updated": C.now()})
    return _reply(c, me)


def delete_for_chats(chats):
    """Before chats are deleted (demo removal): their plans go too."""
    try:
        for c in chats:
            for m in app_tables.meetups.search(chat=c):
                m.delete()
    except Exception:
        pass
