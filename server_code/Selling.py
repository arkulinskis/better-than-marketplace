"""Selling: photos, posting, editing, reserved / sold, bumping, deleting, and "my stuff".

The phone does the heavy lifting: it shrinks each photo (a full JPEG and a small thumbnail) and uploads it
the moment it's taken (upload_photo), while the seller types the name. create_listing then attaches the
uploaded photos. Photos nobody attached are cleaned up after a day.
Photos are served by the /photo endpoint (Photos.py) under their random key.
"""
import base64
import datetime as dt

import anvil
import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables
import anvil.tables.query as q

from . import common as C
from . import Market

MAX_PHOTOS = 8
MAX_FULL = 3 * 1024 * 1024
MAX_THUMB = 600 * 1024
MAX_PENDING = 16
MAX_LIVE = 150
MAX_PRICE = 1000000
STATUSES = ("active", "reserved", "sold")


def _image(data_url, limit):
    """data:image/...;base64,... -> BlobMedia, only real JPEG / PNG / WebP pictures."""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/") or ";base64," not in data_url:
        return None
    if len(data_url) > limit * 4 // 3 + 200:
        return None
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=False)
    except Exception:
        return None
    if raw[:3] == b"\xff\xd8\xff":
        kind = "image/jpeg"
    elif raw[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "image/png"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        kind = "image/webp"
    else:
        return None
    if len(raw) > limit:
        return None
    return anvil.BlobMedia(kind, raw, name="photo." + kind.split("/")[1])


def _cleanup_pending(me):
    old = C.now() - dt.timedelta(days=1)
    for p in app_tables.photos.search(owner=me, listing=None):
        if p["created"] < old:
            p.delete()


@anvil.server.callable(require_user=True)
def upload_photo(full, thumb):
    """One photo, straight after it's taken. Returns its key; create_listing / update_listing attach it."""
    me = C.require_adult()
    if C.rate_limited("photo", 80, 3600):
        return C.fail("That's a lot of photos in one hour. Please take a short break.")
    img, th = _image(full, MAX_FULL), _image(thumb, MAX_THUMB)
    if img is None or th is None:
        return C.fail("That picture didn't work. Try another photo (JPEG or PNG).")
    _cleanup_pending(me)
    if len(app_tables.photos.search(owner=me, listing=None)) >= MAX_PENDING:
        return C.fail("Post the item you're working on first, then add more photos.")
    p = app_tables.photos.add_row(owner=me, listing=None, key=C.token(24), image=img, thumb=th, created=C.now(), is_demo=False)
    return C.ok(key=p["key"])


def _fields(title, price_mode, price, note):
    title = C.text(title, 80)
    if len(title) < 2:
        return None, C.fail("Give it a name, like \"Blue armchair\".")
    if price_mode not in Market.PRICE_MODES:
        price_mode = "price" if price not in (None, "") else "offer"
    if price_mode == "price":
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None, C.fail("Type a price, or choose Free or Make an offer.")
        if price != price or price < 0 or price > MAX_PRICE:
            return None, C.fail("That price doesn't look right.")
        price = round(price, 2)
        if price == 0:
            price_mode, price = "free", None
    else:
        price = None
    return {"title": title, "price_mode": price_mode, "price": price, "note": C.text(note, 1000, multiline=True)}, None


def _photos_for(me, keys, listing=None):
    """The photo rows for these keys, in order: the seller's own, unattached or already on this listing."""
    if not isinstance(keys, list) or not keys:
        return None, C.fail("Add at least one photo.")
    if len(keys) > MAX_PHOTOS:
        return None, C.fail("Up to %d photos per item." % MAX_PHOTOS)
    rows = []
    for k in keys:
        p = app_tables.photos.get(key=k) if isinstance(k, str) and k else None
        if p is None or p["owner"] != me or (p["listing"] is not None and p["listing"] != listing):
            return None, C.fail("One of the photos is missing. Take it again?")
        if p not in rows:
            rows.append(p)
    return rows, None


@anvil.server.callable(require_user=True)
def create_listing(title, price_mode, price, note, photo_keys):
    me = C.require_adult()
    if not C.has_spot(me):
        return C.fail("Set where you sell from first.")
    fields, problem = _fields(title, price_mode, price, note)
    if problem:
        return problem
    photos, problem = _photos_for(me, photo_keys)
    if problem:
        return problem
    if C.rate_limited("listing", 40, 3600):
        return C.fail("That's a lot of items in one hour. Please take a break and post the rest later.")
    if len(app_tables.listings.search(owner=me, status=q.any_of("active", "reserved"))) >= MAX_LIVE:
        return C.fail("You have %d items for sale. Mark some as sold first." % MAX_LIVE)
    now = C.now()
    r = app_tables.listings.add_row(owner=me, key=C.token(10), status="active", area=me["spot_label"], lat=me["spot_lat"],
                                    lng=me["spot_lng"], photo_keys=[p["key"] for p in photos], created=now, bumped=now,
                                    views=0, hidden=False, is_demo=False, **fields)
    for p in photos:
        p["listing"] = r
    return C.ok(key=r["key"], posted=len(app_tables.listings.search(owner=me)))


def _own(key):
    me = C.require_user()
    r = Market.listing_by_key(key)
    if r is None or r["status"] not in STATUSES:
        return me, None, C.fail("That item doesn't exist any more.")
    if r["owner"] != me:
        return me, None, C.fail("That's not your item.")
    return me, r, None


@anvil.server.callable(require_user=True)
def get_for_edit(key):
    me, r, problem = _own(key)
    if problem:
        return problem
    return C.ok(item={"key": r["key"], "title": r["title"], "price": r["price"], "price_mode": r["price_mode"],
                      "note": r["note"] or "", "photo_keys": r["photo_keys"] or [], "status": r["status"]})


@anvil.server.callable(require_user=True)
def update_listing(key, title, price_mode, price, note, photo_keys):
    me, r, problem = _own(key)
    if problem:
        return problem
    fields, problem = _fields(title, price_mode, price, note)
    if problem:
        return problem
    photos, problem = _photos_for(me, photo_keys, r)
    if problem:
        return problem
    keep = {p["key"] for p in photos}
    for p in app_tables.photos.search(listing=r):
        if p["key"] not in keep:
            p.delete()
    for p in photos:
        p["listing"] = r
    r.update(photo_keys=[p["key"] for p in photos], **fields)
    for c in app_tables.chats.search(listing=r):
        c["title"] = fields["title"]
    return C.ok(key=r["key"])


@anvil.server.callable(require_user=True)
def set_listing_status(key, status):
    me, r, problem = _own(key)
    if problem:
        return problem
    if status not in STATUSES:
        return C.fail("Unknown status.")
    r.update(status=status, sold_at=C.now() if status == "sold" else None)
    return C.ok(status=status)


@anvil.server.callable(require_user=True)
def bump_listing(key):
    """Back to the top of the feed, once a day."""
    me, r, problem = _own(key)
    if problem:
        return problem
    if r["status"] not in Market.LIVE:
        return C.fail("Only items for sale can be bumped.")
    wait = Market._bump_wait(r)
    if wait:
        return C.fail("You can bump this again in %d hour%s." % (wait, "" if wait == 1 else "s"))
    r["bumped"] = C.now()
    return C.ok()


def delete_listing_row(r):
    """Delete a listing with its photos, saves and reports. Chats stay (with the item's name) but lose the link."""
    for c in app_tables.chats.search(listing=r):
        c["listing"] = None
    for t in (app_tables.photos, app_tables.saves, app_tables.reports):
        for x in t.search(listing=r):
            x.delete()
    r.delete()


@anvil.server.callable(require_user=True)
def delete_listing(key):
    me = C.require_user()
    r = Market.listing_by_key(key)
    if r is None:
        return C.ok()
    if r["owner"] != me and not C.is_admin(me):
        return C.fail("That's not your item.")
    delete_listing_row(r)
    return C.ok()


@anvil.server.callable(require_user=True)
def my_listings():
    """Everything I sell, by status, with how it's doing."""
    me = C.require_user()
    rows = app_tables.listings.search(tables.order_by("bumped", ascending=False), owner=me)
    out = {"active": [], "reserved": [], "sold": []}
    for r in rows:
        if r["status"] not in out:
            continue
        c = Market.card(r, me)
        c.update(views=r["views"] or 0, chats=len(app_tables.chats.search(listing=r)), can_bump=Market._bump_wait(r) == 0,
                 hidden_reason=r["hidden_reason"] if r["hidden"] else None)
        out[r["status"]].append(c)
    out["sold"].sort(key=lambda c: c["sold_at"] or "", reverse=True)
    return {"lists": out, "spot": {"label": me["spot_label"]} if C.has_spot(me) else None,
            "saved": len(app_tables.saves.search(user=me))}
