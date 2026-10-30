"""Admin page callables: overview, listings (hide / delete), reports, users (make admin, disable), demo data.
Admins only. Feedback admin calls live in Feedback.py."""
import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables
import anvil.tables.query as q

from . import common as C
from . import DemoData, Feedback, Market, Selling


@anvil.server.callable(require_user=True)
def admin_overview():
    C.require_admin()
    return {"users": len([u for u in app_tables.users.search() if not u["is_demo"]]),
            "admins": len(app_tables.users.search(is_admin=True)),
            "feedback_new": Feedback.new_count(),
            "listings": len([r for r in app_tables.listings.search(status=q.any_of(*Market.LIVE))]),
            "sold": len(app_tables.listings.search(status="sold")),
            "chats": len(app_tables.chats.search()),
            "reports_open": len(app_tables.reports.search(status="open")),
            "hidden": len(app_tables.listings.search(hidden=True)),
            "demo": {"state": DemoData.state(), "counts": DemoData.counts()}}


def _user(u):
    return {"id": u.get_id(), "email": u["email"], "name": C.name_of(u), "is_admin": C.is_admin(u),
            "enabled": u["enabled"] is not False, "joined": C.iso(u["signed_up"]), "last_seen": C.iso(u["last_seen"])}


@anvil.server.callable(require_user=True)
def list_users(query=None):
    C.require_admin()
    query = C.text(query, 80).lower()
    rows = [u for u in app_tables.users.search(tables.order_by("signed_up", ascending=False)) if not u["is_demo"]]
    if query:
        rows = [u for u in rows if query in (u["email"] or "").lower() or query in (u["display_name"] or "").lower()]
    return {"users": [_user(u) for u in rows[:200]], "total": len(rows)}


@anvil.server.callable(require_user=True)
def set_admin(user_id, flag):
    me = C.require_admin()
    u = C.row_by_id(app_tables.users, user_id)
    if u is None:
        return C.fail("That account no longer exists.")
    if u == me and not flag:
        return C.fail("You can't remove your own admin rights.")
    u["is_admin"] = bool(flag)
    return C.ok(user=_user(u))


@anvil.server.callable(require_user=True)
def set_enabled(user_id, flag):
    me = C.require_admin()
    u = C.row_by_id(app_tables.users, user_id)
    if u is None:
        return C.fail("That account no longer exists.")
    if u == me:
        return C.fail("You can't disable your own account.")
    u["enabled"] = bool(flag)
    return C.ok(user=_user(u))


@anvil.server.callable(require_user=True)
def demo_load():
    C.require_admin()
    DemoData.load()
    return C.ok(demo={"state": DemoData.state(), "counts": DemoData.counts()})


@anvil.server.callable(require_user=True)
def demo_remove():
    C.require_admin()
    DemoData.remove()
    return C.ok(demo={"state": DemoData.state(), "counts": DemoData.counts()})


def _admin_card(r):
    c = Market.card(r)
    owner = r["owner"]
    c.update(owner=C.name_of(owner), owner_email=owner["email"] if owner and not owner["is_demo"] else None,
             owner_key=C.public_key(owner) if owner else None, hidden_reason=r["hidden_reason"],
             reports=len(app_tables.reports.search(listing=r, status="open")), views=r["views"] or 0)
    return c


@anvil.server.callable(require_user=True)
def admin_listings(query=None, which="all"):
    """Every listing, newest first; which = all | hidden | reported | sold."""
    C.require_admin()
    query = C.text(query, 80).lower()
    rows = list(app_tables.listings.search(tables.order_by("created", ascending=False)))
    if which == "hidden":
        rows = [r for r in rows if r["hidden"]]
    elif which == "reported":
        rows = [r for r in rows if app_tables.reports.search(listing=r, status="open")]
    elif which == "sold":
        rows = [r for r in rows if r["status"] == "sold"]
    if query:
        rows = [r for r in rows if query in (r["title"] or "").lower() or query in (r["area"] or "").lower()
                or query in C.name_of(r["owner"]).lower()]
    return {"items": [_admin_card(r) for r in rows[:120]], "total": len(rows)}


@anvil.server.callable(require_user=True)
def admin_set_hidden(key, flag, reason=""):
    C.require_admin()
    r = Market.listing_by_key(key)
    if r is None:
        return C.fail("That listing no longer exists.")
    r.update(hidden=bool(flag), hidden_reason=(C.text(reason, 200) or "Hidden by a moderator.") if flag else None)
    if not flag:
        for x in app_tables.reports.search(listing=r, status="open"):
            x["status"] = "dismissed"
    return C.ok(item=_admin_card(r))


@anvil.server.callable(require_user=True)
def admin_reports(status="open"):
    C.require_admin()
    status = status if status in ("open", "done", "dismissed") else "open"
    rows = app_tables.reports.search(tables.order_by("created", ascending=False), status=status)
    out = []
    for x in rows[:200]:
        r = x["listing"]
        out.append({"id": x.get_id(), "reason": Market.REPORT_REASONS.get(x["reason"], x["reason"]), "details": x["details"] or "",
                    "created": C.iso(x["created"]), "reporter": C.name_of(x["reporter"]), "status": x["status"],
                    "listing": _admin_card(r) if r is not None else None})
    return {"reports": out, "open": len(app_tables.reports.search(status="open"))}


@anvil.server.callable(require_user=True)
def admin_resolve_report(report_id, action):
    """dismiss (the listing is fine: un-hide it) | hide (keep it hidden) | delete (remove the listing)."""
    C.require_admin()
    x = C.row_by_id(app_tables.reports, report_id)
    if x is None:
        return C.fail("That report no longer exists.")
    r = x["listing"]
    if action == "dismiss":
        x["status"] = "dismissed"
        if r is not None and not app_tables.reports.search(listing=r, status="open"):
            r.update(hidden=False, hidden_reason=None)
    elif action == "hide":
        if r is not None:
            r.update(hidden=True, hidden_reason="Hidden by a moderator after a report.")
            for y in app_tables.reports.search(listing=r, status="open"):
                y["status"] = "done"
        x["status"] = "done"
    elif action == "delete":
        if r is not None:
            Selling.delete_listing_row(r)
        else:
            x.delete()
    else:
        return C.fail("Unknown action.")
    return C.ok()
