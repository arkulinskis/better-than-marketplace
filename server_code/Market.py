"""Browsing what people sell: the feed, one listing, a seller's page, saved items and reports.

Anyone can browse (signed out too). Saving, messaging and reporting need an account.
Locations: a listing keeps its seller's spot (~100 m). Other people only ever get a distance and the
area name, plus a point rounded to ~1 km for the map circle on the listing page.
"""
import datetime as dt
import math

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables
import anvil.tables.query as q

from . import common as C
from . import DemoData

LIVE = ("active", "reserved")
PRICE_MODES = ("price", "free", "offer")
REPORT_REASONS = {"prohibited": "Not allowed here", "scam": "Scam or spam", "offensive": "Offensive",
                  "wrong": "Misleading photos or info", "other": "Something else"}
AUTO_HIDE_REPORTS = 3   # open reports from different people hide a listing until an admin looks
SOLD_SHOWN_DAYS = 30    # sold items stay on the seller's page this long


def origin_for(opts, me):
    """Where distances are measured from: the browser's spot if it sent one, else the member's selling spot."""
    opts = opts if isinstance(opts, dict) else {}
    lat, lng = C.coord(opts.get("lat"), 90), C.coord(opts.get("lng"), 180)
    if lat is not None and lng is not None:
        return {"lat": lat, "lng": lng, "label": C.text(opts.get("label"), 60) or "your spot"}
    if C.has_spot(me):
        return {"lat": me["spot_lat"], "lng": me["spot_lng"], "label": me["spot_label"]}
    return None


def dist(r, origin):
    if origin is None or r["lat"] is None or r["lng"] is None:
        return None
    return round(C.km_between(origin["lat"], origin["lng"], r["lat"], r["lng"]), 1)


def card(r, me=None, origin=None, saved=None):
    keys = r["photo_keys"] or []
    return {"key": r["key"], "title": r["title"], "price": r["price"], "price_mode": r["price_mode"] or "price",
            "status": r["status"], "area": r["area"] or "", "dist": dist(r, origin), "cover": keys[0] if keys else None,
            "photos": len(keys), "posted": C.iso(r["bumped"] or r["created"]), "sold_at": C.iso(r["sold_at"]),
            "demo": bool(r["is_demo"]), "mine": me is not None and r["owner"] == me,
            "saved": bool(saved is not None and r["key"] in saved), "hidden": bool(r["hidden"])}


def saved_keys(me):
    if me is None:
        return set()
    return {s["listing"]["key"] for s in app_tables.saves.search(user=me) if s["listing"] is not None}


def listing_by_key(key):
    if not isinstance(key, str) or not key or len(key) > 40:
        return None
    return app_tables.listings.get(key=key)


def can_see(r, me):
    if r is None or r["status"] not in ("active", "reserved", "sold"):
        return False
    return not r["hidden"] or (me is not None and (r["owner"] == me or C.is_admin(me)))


@anvil.server.callable
def browse(opts=None):
    """The feed. opts: lat, lng, label (the viewer's spot), radius (km, 0 = anywhere), q (words),
    filter ('all' | 'free' | 'under20' | 'today'), sort ('near' | 'new' | 'cheap'), offset, limit."""
    DemoData.ensure_loaded()
    opts = opts if isinstance(opts, dict) else {}
    me = C.me()
    origin = origin_for(opts, me)
    radius = opts.get("radius")
    radius = float(radius) if isinstance(radius, (int, float)) and not isinstance(radius, bool) and 0 < radius <= 500 else 0
    sort = opts.get("sort") if opts.get("sort") in ("near", "new", "cheap") else ("near" if origin else "new")
    if sort == "near" and origin is None:
        sort = "new"
    flt = opts.get("filter") if opts.get("filter") in ("all", "free", "under20", "today") else "all"
    words = [w for w in C.text(opts.get("q"), 80).lower().split(" ") if w]
    offset = opts.get("offset") if isinstance(opts.get("offset"), int) and opts.get("offset") > 0 else 0
    limit = opts.get("limit") if isinstance(opts.get("limit"), int) and 1 <= opts.get("limit") <= 60 else 24

    query = {"status": q.any_of(*LIVE), "hidden": False}
    if origin and radius:
        dlat = radius / 111.0
        dlng = radius / max(1.0, 111.0 * abs(math.cos(math.radians(origin["lat"]))))
        query["lat"] = q.between(origin["lat"] - dlat, origin["lat"] + dlat)
        query["lng"] = q.between(origin["lng"] - dlng, origin["lng"] + dlng)
    rows = list(app_tables.listings.search(**query))
    out = []
    day_ago = C.now() - dt.timedelta(days=1)
    for r in rows:
        d = dist(r, origin)
        if origin and radius and (d is None or d > radius):
            continue
        if flt == "free" and r["price_mode"] != "free":
            continue
        if flt == "under20" and not (r["price_mode"] == "free" or (r["price_mode"] == "price" and (r["price"] or 0) <= 20)):
            continue
        if flt == "today" and (r["bumped"] or r["created"]) < day_ago:
            continue
        if words:
            hay = ((r["title"] or "") + " " + (r["note"] or "") + " " + (r["area"] or "")).lower()
            if not all(w in hay for w in words):
                continue
        out.append((r, d))
    newest = lambda x: (x[0]["bumped"] or x[0]["created"]).timestamp()  # noqa: E731
    if sort == "near":
        out.sort(key=lambda x: (x[1] if x[1] is not None else 9e9, -newest(x)))
    elif sort == "cheap":
        out.sort(key=lambda x: (0 if x[0]["price_mode"] == "free" else 1 if x[0]["price_mode"] == "price" else 2,
                                x[0]["price"] or 0, -newest(x)))
    else:
        out.sort(key=lambda x: -newest(x))
    # reserved items sink below available ones, keeping the chosen order within each group
    out.sort(key=lambda x: x[0]["status"] == "reserved")
    saved = saved_keys(me)
    page = out[offset:offset + limit]
    return {"items": [card(r, me, origin, saved) for r, _ in page], "total": len(out), "sort": sort,
            "origin": {"label": origin["label"]} if origin else None,
            "next": offset + limit if offset + limit < len(out) else None}


def seller_dict(u):
    sold = len([r for r in app_tables.listings.search(owner=u, status="sold")])
    active = len([r for r in app_tables.listings.search(owner=u, status=q.any_of(*LIVE), hidden=False)])
    return {"key": C.public_key(u), "name": C.name_of(u), "since": C.iso(u["signed_up"]), "area": u["spot_label"] or "",
            "sold": sold, "active": active, "demo": bool(u["is_demo"])}


@anvil.server.callable
def get_listing(key, opts=None):
    """One listing with everything its page shows."""
    DemoData.ensure_loaded()
    me = C.me()
    r = listing_by_key(key)
    if not can_see(r, me):
        return C.fail("This item isn't available any more.")
    mine = me is not None and r["owner"] == me
    if not mine:
        seen = anvil.server.session.get("seen") or []
        if r["key"] not in seen:
            r["views"] = (r["views"] or 0) + 1
            anvil.server.session["seen"] = (seen + [r["key"]])[-200:]
    origin = origin_for(opts, me)
    saved = saved_keys(me)
    out = card(r, me, origin, saved)
    seller = r["owner"]
    chat = None
    if me is not None and not mine:
        c = app_tables.chats.get(listing=r, buyer=me)
        chat = c["key"] if c else None
    more = [x for x in app_tables.listings.search(tables.order_by("bumped", ascending=False), owner=seller,
                                                   status=q.any_of(*LIVE), hidden=False) if x != r][:6]
    out.update(photo_keys=r["photo_keys"] or [], note=r["note"] or "", created=C.iso(r["created"]),
               map={"lat": round(r["lat"], 2), "lng": round(r["lng"], 2)} if r["lat"] is not None else None,
               seller=seller_dict(seller), chat=chat, can_edit=mine, can_delete=mine or C.is_admin(me),
               views=(r["views"] or 0) if mine or C.is_admin(me) else None,
               chats=len(app_tables.chats.search(listing=r)) if mine else None,
               can_bump=mine and r["status"] in LIVE and _bump_wait(r) == 0, hidden_reason=r["hidden_reason"] if mine else None,
               more=[card(x, me, origin, saved) for x in more])
    return C.ok(item=out)


def _bump_wait(r):
    """Hours until this listing can be bumped again (once a day)."""
    last = r["bumped"] or r["created"]
    left = 24 - (C.now() - last).total_seconds() / 3600.0
    return max(0, int(left + 0.999))


@anvil.server.callable
def seller_page(user_key, opts=None):
    """A seller's public page: who they are, what they sell, what they sold lately."""
    DemoData.ensure_loaded()
    if not isinstance(user_key, str) or not user_key:
        return C.fail("That seller doesn't exist.")
    u = app_tables.users.get(public_key=user_key)
    if u is None or u["enabled"] is False and not u["is_demo"]:
        return C.fail("That seller doesn't exist.")
    me = C.me()
    origin = origin_for(opts, me)
    saved = saved_keys(me)
    live = app_tables.listings.search(tables.order_by("bumped", ascending=False), owner=u, status=q.any_of(*LIVE), hidden=False)
    since = C.now() - dt.timedelta(days=SOLD_SHOWN_DAYS)
    sold = [r for r in app_tables.listings.search(tables.order_by("sold_at", ascending=False), owner=u, status="sold")
            if r["sold_at"] and r["sold_at"] >= since and not r["hidden"]]
    return C.ok(seller=seller_dict(u), mine=me is not None and u == me,
                items=[card(r, me, origin, saved) for r in live], sold=[card(r, me, origin, saved) for r in sold[:12]])


@anvil.server.callable(require_user=True)
def toggle_save(key):
    me = C.require_user()
    r = listing_by_key(key)
    if not can_see(r, me):
        return C.fail("This item isn't available any more.")
    s = app_tables.saves.get(user=me, listing=r)
    if s:
        s.delete()
        return C.ok(saved=False)
    if len(app_tables.saves.search(user=me)) >= 300:
        return C.fail("You've saved 300 items. Unsave a few first.")
    app_tables.saves.add_row(user=me, listing=r, created=C.now(), is_demo=False)
    return C.ok(saved=True)


@anvil.server.callable(require_user=True)
def my_saved(opts=None):
    me = C.require_user()
    origin = origin_for(opts, me)
    rows = [s["listing"] for s in app_tables.saves.search(tables.order_by("created", ascending=False), user=me)]
    rows = [r for r in rows if r is not None and can_see(r, me)]
    keys = {r["key"] for r in rows}
    return {"items": [card(r, me, origin, keys) for r in rows]}


@anvil.server.callable(require_user=True)
def report_listing(key, reason, details=""):
    me = C.require_user()
    r = listing_by_key(key)
    if not can_see(r, me):
        return C.fail("This item isn't available any more.")
    if r["owner"] == me:
        return C.fail("That's your own listing.")
    if reason not in REPORT_REASONS:
        return C.fail("Pick a reason.")
    if C.rate_limited("report", 10, 3600):
        return C.fail("You've sent a lot of reports this hour. Please try again later.")
    if app_tables.reports.get(listing=r, reporter=me, status="open"):
        return C.ok(already=True)
    app_tables.reports.add_row(listing=r, reporter=me, reason=reason, details=C.text(details, 600, multiline=True),
                               status="open", created=C.now(), is_demo=False)
    reporters = {x["reporter"].get_id() for x in app_tables.reports.search(listing=r, status="open") if x["reporter"]}
    if len(reporters) >= AUTO_HIDE_REPORTS and not r["hidden"]:
        r.update(hidden=True, hidden_reason="Hidden while we look at reports from other members.")
    return C.ok()
