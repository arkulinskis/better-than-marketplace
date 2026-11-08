"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python tools/testing/test_server.py          -> prints ALL OK, or the first failure

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
from anvil.tables import app_tables as T  # noqa: E402

M = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)


# ---------------------------------------------------------------------------------- accounts
admin = person("arkulinskis@gmail.com", "The Admin")
ana = person("ana@example.com", "Ana")
bob = person("bob@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bob", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#home", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == 3 and ov["admins"] == 1 and ov["feedback_new"] == 5 and ov["listings"] >= 0
assert len(call("list_users")["users"]) == 3 and len(call("list_users", "bob")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False

# ---------------------------------------------------------------------------------- 18+ and the selling spot
import base64  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

as_user(None)
assert denied("finish_signup", "X", "1990-01-01") and denied("set_spot", "x", 1, 1) and denied("confirm_age", "1990-01-01")
kid = person("kid@example.com", "Kid")
as_user(kid)
young = (now.date().replace(year=now.date().year - 15)).isoformat()
bad(call("finish_signup", "Kid", young))
assert kid["enabled"] is False and kid["adult_confirmed_at"] is None, "an under-18 account is switched off"
as_user(ana)
bad(call("finish_signup", "Ana", "not a date"))
bad(call("finish_signup", "Ana", "2999-01-01"))
r = ok(call("finish_signup", "Ana Lima", "1992-04-12"))
assert r["me"]["adult"] and r["me"]["name"] == "Ana Lima" and r["me"]["spot"] is None and ana["adult_confirmed_at"]
bad(call("set_spot", "x", 45.5, -73.5), "a name is needed")
bad(call("set_spot", "Plateau", None, -73.5), "a point is needed")
bad(call("set_spot", "Plateau", 145, -73.5), "a real latitude")
r = ok(call("set_spot", "Plateau", 45.52512345, -73.58234567))
assert r["me"]["spot"] == {"label": "Plateau", "lat": 45.525, "lng": -73.582}, "kept to ~100 m"
as_user(bob)
ok(call("confirm_age", "1985-09-30"))
ok(call("set_spot", "Verdun", 45.459, -73.569))

# ---------------------------------------------------------------------------------- browsing (public)
as_user(None)
feed = call("browse", {})
assert M["DemoData"].state() == "loaded", "demo loads on first visit"
live = [x for x in M["DemoData"].DEMO_LISTINGS if x[7] in ("active", "reserved")]
assert feed["total"] == len(live) and feed["sort"] == "new" and feed["origin"] is None
assert all(it["dist"] is None for it in feed["items"]) and not any(it["saved"] for it in feed["items"])
assert [it["status"] for it in feed["items"]][-1] == "reserved" or len(feed["items"]) < feed["total"], "reserved items sink"
near = call("browse", {"lat": 45.5246, "lng": -73.5996, "label": "Mile End", "radius": 1})
assert near["sort"] == "near" and near["items"] and all(it["dist"] <= 1 for it in near["items"]) and near["origin"]["label"] == "Mile End"
assert call("browse", {"lat": 45.5246, "lng": -73.5996, "radius": 25})["total"] == len(live)
free = call("browse", {"filter": "free"})
assert free["items"] and all(it["price_mode"] == "free" for it in free["items"])
cheap = call("browse", {"filter": "under20"})["items"]
assert cheap and all(it["price_mode"] == "free" or it["price"] <= 20 for it in cheap)
assert call("browse", {"q": "ARMCHAIR"})["total"] == 1 and call("browse", {"q": "zebra"})["total"] == 0
page1 = call("browse", {"limit": 5})
assert len(page1["items"]) == 5 and page1["next"] == 5 and call("browse", {"limit": 5, "offset": 5})["items"][0]["key"] != page1["items"][0]["key"]
srt = call("browse", {"sort": "cheap"})["items"]
assert srt[0]["price_mode"] == "free"
call("browse", {"lat": "x", "lng": None, "radius": "far", "sort": "weird", "filter": 7, "offset": -3, "limit": 9999})  # junk is ignored
chair = T.listings.get(title="Yellow velvet armchair")
it = ok(call("get_listing", chair["key"]))["item"]
assert it["seller"]["name"] == "Maya Chen" and len(it["photo_keys"]) == 3 and it["views"] is None and not it["can_edit"]
assert it["map"] == {"lat": 45.52, "lng": -73.6} and "email" not in json.dumps(it["seller"])
v = chair["views"]
call("get_listing", chair["key"])
assert chair["views"] == v, "a view counts once per session"
bad(call("get_listing", "nope"))
sold_demo = T.listings.get(title="Road bike (older)")
assert ok(call("get_listing", sold_demo["key"]))["item"]["status"] == "sold", "sold items still have their page"
sp = ok(call("seller_page", it["seller"]["key"]))
assert sp["seller"]["sold"] == 1 and len(sp["sold"]) == 1 and all(x["status"] != "sold" for x in sp["items"])
bad(call("seller_page", "nope"))
assert denied("toggle_save", chair["key"]) and denied("my_saved") and denied("report_listing", chair["key"], "scam")

# ---------------------------------------------------------------------------------- photos endpoint
ep = anvil.server.ENDPOINTS["/photo"]
first = it["photo_keys"][0]
resp = ep(k=first, s="t")
assert resp.status == 200 and resp.body.content_type == "image/svg+xml" and b"<svg" in resp.body.get_bytes()
assert ep(k="nope").status == 404 and ep().status == 404

# ---------------------------------------------------------------------------------- selling
JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 200).decode()
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 50).decode()
SVG = "data:image/svg+xml;base64," + base64.b64encode(b"<svg onload=alert(1)>").decode()
as_user(None)
assert denied("upload_photo", JPEG, JPEG) and denied("create_listing", "x", "price", 5, "", [])
carol = person("carol@example.com", "Carol")
as_user(carol)
assert denied("upload_photo", JPEG, JPEG), "18+ must be confirmed before uploading"
ok(call("confirm_age", "1990-01-01"))
pk = ok(call("upload_photo", JPEG, JPEG))["key"]
bad(call("create_listing", "Lamp", "price", 5, "", [pk]), "no selling spot yet")
as_user(ana)
bad(call("upload_photo", SVG, SVG), "only real photos")
bad(call("upload_photo", "nonsense", JPEG))
p1 = ok(call("upload_photo", JPEG, JPEG))["key"]
p2 = ok(call("upload_photo", PNG, PNG))["key"]
assert ep(k=p1).status == 404, "photos still being posted aren't served"
bad(call("create_listing", " ", "price", 5, "", [p1]), "needs a name")
bad(call("create_listing", "Lamp", "price", None, "", [p1]), "price mode needs a price")
bad(call("create_listing", "Lamp", "price", -5, "", [p1]))
bad(call("create_listing", "Lamp", "price", 5, "", []), "needs a photo")
bad(call("create_listing", "Lamp", "price", 5, "", [pk]), "someone else's photo")
bad(call("create_listing", "Lamp", "price", 5, "", ["x"] * 9))
r = ok(call("create_listing", "  Brass desk lamp ", "price", "12.5", "Works great.\n\nBulb included.", [p2, p1]))
lamp = T.listings.get(key=r["key"])
assert lamp["title"] == "Brass desk lamp" and lamp["price"] == 12.5 and lamp["photo_keys"] == [p2, p1] and lamp["area"] == "Plateau" and lamp["status"] == "active"
assert ep(k=p1).status == 200 and ep(k=p1, s="t").body.content_type == "image/jpeg"
bad(call("create_listing", "Again", "price", 3, "", [p1]), "a photo can't go on two listings")
free_r = ok(call("create_listing", "Old magazines", "price", 0, "", [ok(call("upload_photo", JPEG, JPEG))["key"]]))
assert T.listings.get(key=free_r["key"])["price_mode"] == "free", "a price of 0 is free"
offer_r = ok(call("create_listing", "Mystery box", "offer", 99, "", [ok(call("upload_photo", JPEG, JPEG))["key"]]))
assert T.listings.get(key=offer_r["key"])["price"] is None
mine = call("my_listings")
assert len(mine["lists"]["active"]) == 3 and mine["spot"]["label"] == "Plateau"
it = ok(call("get_listing", lamp["key"]))["item"]
assert it["can_edit"] and it["views"] == 0 and it["chats"] == 0 and it["mine"] and not it["can_bump"]
bad(call("bump_listing", lamp["key"]), "once a day")
lamp["bumped"] = now - dt.timedelta(hours=25)
ok(call("bump_listing", lamp["key"]))
ed = ok(call("get_for_edit", lamp["key"]))["item"]
assert ed["photo_keys"] == [p2, p1]
p3 = ok(call("upload_photo", JPEG, JPEG))["key"]
ok(call("update_listing", lamp["key"], "Brass lamp", "free", None, "", [p3, p2]))
assert lamp["title"] == "Brass lamp" and lamp["price_mode"] == "free" and lamp["photo_keys"] == [p3, p2]
assert T.photos.get(key=p1) is None, "a photo taken off the listing is deleted"
ok(call("set_listing_status", lamp["key"], "reserved"))
bad(call("set_listing_status", lamp["key"], "gone"))
as_user(bob)
bad(call("update_listing", lamp["key"], "Mine now", "free", None, "", [p3]))
bad(call("set_listing_status", lamp["key"], "sold"))
bad(call("delete_listing", lamp["key"]))
bad(call("get_for_edit", lamp["key"]))
# moving your spot moves what you sell
as_user(ana)
ok(call("set_spot", "Mile End", 45.524, -73.6))
assert lamp["area"] == "Mile End" and lamp["lat"] == 45.524

# ---------------------------------------------------------------------------------- saves
as_user(bob)
assert ok(call("toggle_save", lamp["key"]))["saved"] is True
assert [x["key"] for x in call("my_saved")["items"]] == [lamp["key"]]
assert [x["saved"] for x in call("browse", {"q": "brass"})["items"] if x["key"] == lamp["key"]] == [True]
assert ok(call("toggle_save", lamp["key"]))["saved"] is False and call("my_saved")["items"] == []
ok(call("toggle_save", chair["key"]))
bad(call("toggle_save", "nope"))

# ---------------------------------------------------------------------------------- chats
as_user(ana)
bad(call("start_chat", lamp["key"], "hi"), "not on your own item")
as_user(bob)
bad(call("start_chat", lamp["key"], "   "), "empty message")
bad(call("start_chat", sold_demo["key"], "hi"), "sold items take no new chats")
ck = ok(call("start_chat", lamp["key"], "Hi! Is this still available?"))["chat"]
assert ok(call("start_chat", lamp["key"], "Also, what colour is it?"))["chat"] == ck, "one chat per item and buyer"
as_user(ana)
assert call("badges")["unread"] == 2
lst = call("list_chats")["chats"]
assert len(lst) == 1 and lst[0]["role"] == "selling" and lst[0]["other"] == "Bob Stone" and lst[0]["unread"] == 2 and lst[0]["last_text"] == "Also, what colour is it?"
g = ok(call("get_chat", ck))
assert len(g["messages"]) == 2 and not g["messages"][0]["mine"] and call("badges")["unread"] == 0
after = g["messages"][-1]["at"]
m = ok(call("send_message", ck, "Yes! Brass, a warm gold."))["message"]
assert m["mine"]
as_user(bob)
assert call("badges")["unread"] == 1
pl = ok(call("poll_chat", ck, after))["messages"]
assert pl[-1]["text"] == "Yes! Brass, a warm gold." and m["id"] in [x["id"] for x in pl] and call("badges")["unread"] == 0
assert ok(call("get_listing", lamp["key"]))["item"]["chat"] == ck
as_user(carol)
bad(call("get_chat", ck), "outsiders can't read a chat")
bad(call("send_message", ck, "hi"))
bad(call("poll_chat", ck))
as_user(None)
assert denied("list_chats") and denied("badges") and denied("get_chat", ck)

# ---------------------------------------------------------------------------------- reports, auto-hide, admin moderation
dave = person("dave@example.com", "Dave")
for who in (bob, carol, dave):
    as_user(who)
    bad(call("report_listing", lamp["key"], "weird"), "needs a known reason")
    ok(call("report_listing", lamp["key"], "scam", "Looks fake"))
    if who is bob:
        assert ok(call("report_listing", lamp["key"], "scam"))["already"] is True, "one open report per person"
assert lamp["hidden"] is True, "three reports hide an item"
assert lamp["key"] not in [x["key"] for x in call("browse", {"q": "brass"})["items"]]
bad(call("get_listing", lamp["key"]), "hidden items are gone for others")
as_user(ana)
bad(call("report_listing", lamp["key"], "scam"), "not your own")
assert ok(call("get_listing", lamp["key"]))["item"]["hidden"], "the owner still sees it"
for fn, args in [("admin_listings", ()), ("admin_set_hidden", (lamp["key"], False)), ("admin_reports", ()), ("admin_resolve_report", ("x", "dismiss"))]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["reports_open"] == 3 and ov["hidden"] == 1 and ov["chats"] == 1
assert call("admin_listings", None, "reported")["total"] == 1 and call("admin_listings", "brass")["items"][0]["owner_email"] == "ana@example.com"
assert call("admin_listings", None, "hidden")["total"] == 1 and call("admin_listings", None, "sold")["total"] >= 3
reps = call("admin_reports")["reports"]
assert len(reps) == 3 and reps[0]["listing"]["key"] == lamp["key"]
ok(call("admin_resolve_report", reps[0]["id"], "dismiss"))
assert lamp["hidden"] is True, "still hidden while other reports are open"
ok(call("admin_set_hidden", lamp["key"], False))
assert lamp["hidden"] is False and call("admin_reports")["open"] == 0, "showing it again closes the reports"
ok(call("admin_set_hidden", lamp["key"], True, "Checking"))
assert lamp["hidden_reason"] == "Checking"
ok(call("admin_set_hidden", lamp["key"], False))
bad(call("admin_resolve_report", reps[0]["id"], "explode"))
bad(call("admin_resolve_report", "nope", "hide"))
as_user(carol)
ok(call("report_listing", offer_r["key"], "offensive"))
as_user(admin)
rid = call("admin_reports")["reports"][0]["id"]
ok(call("admin_resolve_report", rid, "hide"))
assert T.listings.get(key=offer_r["key"])["hidden"] and call("admin_reports", "done")["reports"]
ok(call("delete_listing", offer_r["key"]), "admins can delete anything")
assert T.listings.get(key=offer_r["key"]) is None

# ---------------------------------------------------------------------------------- deleting keeps the chat, with the item's name
as_user(ana)
ok(call("set_listing_status", lamp["key"], "sold"))
assert lamp["sold_at"] is not None and call("my_listings")["lists"]["sold"][0]["key"] == lamp["key"]
lamp_key = lamp["key"]
ok(call("delete_listing", lamp_key))
assert T.listings.get(key=lamp_key) is None and T.photos.get(key=p3) is None
c = call("list_chats")["chats"][0]
assert c["status"] == "gone" and c["title"] == "Brass lamp" and c["listing"] is None
ok(call("delete_listing", "gone-already"))

# ---------------------------------------------------------------------------------- demo data
as_user(bob)
ck2 = ok(call("start_chat", chair["key"], "Hello Maya!"))["chat"]
as_user(admin)
real = T.listings.get(title="Old magazines")
ok(call("demo_remove"))
assert M["DemoData"].state() == "removed" and not T.users.search(is_demo=True) and not T.listings.search(is_demo=True)
assert T.chats.get(key=ck2) is None and T.chats.get(key=ck) is not None, "chats with demo sellers go, real ones stay"
assert not T.saves.search(), "saves of demo items go"
as_user(None)
assert call("browse", {})["total"] == 1 and real["status"] == "active", "removing demo data keeps real data"
assert M["DemoData"].state() == "removed", "removed demo data doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
assert call("browse", {})["total"] == 1 + len(live), "reloading replaces the demo instead of doubling it"
for name in M["DemoArt"].NAMES:
    for variant in (0, 1, 2):
        s = M["DemoArt"].svg(name, variant)
        assert s.startswith("<svg") and s.endswith("</svg>"), name
        ET.fromstring(s)  # valid XML (a repeated attribute makes the browser show a broken picture)

# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in M:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"get_me", "submit_feedback", "legal_state", "legal_accept", "browse", "get_listing", "seller_page"}
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
