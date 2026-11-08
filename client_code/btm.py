"""The marketplace's shared client helpers: prices and price stickers, distances, photo URLs, the viewer's spot,
saving (hearts), the 18+ check and the selling-spot picker. Engines (maps, photo shrinking, confetti, share) are
JavaScript in theme/assets/btm.js (window.BTM); this module is the only Python that talks to them."""
import json

from anvil import alert
import anvil.js
from anvil.js import window

from . import router, state

LIVE_STATUSES = ("active", "reserved")


# ---------------------------------------------------------------- formatting
def photo(key, thumb=False):
    return window.BTM.photo(key, bool(thumb)) if key else ""


def money(n):
    return window.BTM.money(n)


def price_mode(it):
    if it.get("price_mode") == "free":
        return "free"
    if it.get("price_mode") == "offer" or it.get("price") is None:
        return "offer"
    return "price"


def price(it):
    mode = price_mode(it)
    if mode == "free":
        return "Free"
    if mode == "offer":
        return "Make an offer"
    return money(it["price"])


def tag(label, it, size=""):
    """Turn a Label into the sunflower price sticker. size: "" (on a card photo), "big" (item page), "inline" (rows)."""
    mode = price_mode(it)
    label.text = "Offer" if mode == "offer" and size != "big" else price(it)
    label.role = ["tag"] + (["tag-" + mode] if mode != "price" else []) + (["tag-" + size] if size else [])


def dist(d):
    if d is None:
        return ""
    if d < 1:
        return "under 1 km"
    if d < 10:
        s = "%.1f" % d
        return (s[:-2] if s.endswith(".0") else s) + " km"
    return "%d km" % round(d)


def first_name(name):
    return (name or "").split(" ")[0]


def long_date(iso):
    """'2026-11-02T...' -> 'November 2026' (member since)."""
    return state.month_year(iso)


# ---------------------------------------------------------------- the viewer's spot (for distances)
# Guests: kept in this browser only. Members: their selling spot, unless they picked another one here.
def _stored_where():
    raw = window.localStorage.getItem(window.UI.config.key + ".where")
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


def where():
    w = _stored_where()
    if isinstance(w, dict) and w.get("anywhere"):
        return None
    if isinstance(w, dict) and w.get("lat") is not None:
        return w
    me = state.me()
    if me and me.get("spot"):
        s = me["spot"]
        return {"lat": s["lat"], "lng": s["lng"], "label": s["label"], "mine": True}
    return None


def set_where(w):
    """w: a spot {lat, lng, label}, "anywhere" (no distances, even for members with a selling spot), or None
    (back to the default: the member's selling spot)."""
    if w == "anywhere":
        value = {"anywhere": True}
    elif isinstance(w, dict) and w.get("lat") is not None:
        value = {"lat": w["lat"], "lng": w["lng"], "label": w.get("label") or "Pinned spot"}
    else:
        value = None
    state.store_set("where", value)


def opts(**extra):
    """The options every listing call sends: where distances are measured from, plus extras (q, filter, sort...)."""
    w = where()
    o = {}
    if w:
        o = {"lat": w["lat"], "lng": w["lng"], "label": w.get("label") or ""}
    o.update(extra)
    return o


# ---------------------------------------------------------------- saving (hearts)
def toggle_save(key):
    """Save / unsave a listing. Visitors are sent to sign up first. Returns True/False (saved now) or None."""
    if not state.me():
        router.remember_after(window.location.hash)
        state.toast("Join (it's free) to save things you like.")
        router.go("auth", "signup")
        return None
    r = state.call("toggle_save", key)
    if r is None:
        return None
    saved = bool(r["saved"])
    # every heart for this listing on the page follows (a card in "More from" and the item's own Save button)
    nodes = window.document.querySelectorAll('[data-save="%s"]' % window.CSS.escape(key))
    for i in range(nodes.length):
        h = getattr(nodes, "item")(i)
        h.classList.toggle("on", saved)
        h.setAttribute("aria-pressed", "true" if saved else "false")
        label = h.querySelector("[data-save-label]")
        if label:
            label.textContent = "Saved" if saved else "Save"
        h.classList.remove("pop")
        if saved:
            _ = h.offsetWidth  # restart the little pop animation
            h.classList.add("pop")
    state.toast("Saved. Find it under My stuff." if saved else "Removed from your saved items.", "ok" if saved else None)
    return saved


# ---------------------------------------------------------------- 18+ and the selling spot
def age_gate():
    """Ask an account that hasn't confirmed its age yet. Returns the updated me, or None."""
    from .Dialogs.AgeGate import AgeGate
    return alert(AgeGate(), buttons=[], role="app-dialog", dismissible=True)


def pick_spot(**options):
    """The map spot picker (Dialogs.SpotPicker). Returns {lat, lng, label}, {"extra": name} or None."""
    from .Dialogs.SpotPicker import SpotPicker
    return alert(SpotPicker(**options), buttons=[], role="app-dialog", large=True, dismissible=True)


def edit_spot():
    """Set (or change) where the signed-in member sells from. Returns the updated me, or None."""
    me = state.me() or {}
    s = me.get("spot") or {}
    p = pick_spot(title="Where do you sell from?", ok="Save my spot",
                  text="Buyers see the area name and how far away you are, never your address. "
                       "Your items for sale move with you.",
                  hint="Tap the map to move the pin. A street corner near you is plenty.",
                  label=s.get("label"), lat=s.get("lat"), lng=s.get("lng"))
    if not p or p.get("extra"):
        return None
    r = state.call("set_spot", p["label"], p["lat"], p["lng"])
    if r is None:
        return None
    state.set_me(r["me"])
    state.toast("Saved: you sell from %s." % r["me"]["spot"]["label"], "ok")
    return r["me"]


def share(it):
    url = str(window.location.href).split("#")[0] + "#item/" + it["key"]
    how = window.BTM.share(it["title"], "%s · %s on Better Than Marketplace" % (it["title"], price(it)), url)
    if how == "copied":
        state.toast("Link copied. Paste it anywhere.", "ok")
    elif how == "manual":
        from anvil import TextBox
        box = TextBox(text=url)
        alert(box, title="Share this item", role="app-dialog")


def confetti():
    window.BTM.confetti()


def media(query):
    """True when a CSS media query matches ("(pointer: fine)" = a mouse, "(pointer: coarse)" = a finger)."""
    return bool(getattr(window.matchMedia(query), "matches"))


def remember_here():
    router.remember_after(window.location.hash)


def js(value):
    """A Python dict/list as a real JS object (for engines that read plain JSON)."""
    return window.JSON.parse(json.dumps(value))


def dom(component):
    return anvil.js.get_dom_node(component)
