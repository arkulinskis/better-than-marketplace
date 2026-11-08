import datetime

from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import SellTemplate
from ... import btm, router, state
from ...Items.Card import Card

MAX = 8
MODES = ("price", "free", "offer")


class Sell(SellTemplate):
    """#sell (post) and #sell/<key> (edit): the snap-and-post flow, members only.
    Before the first post: the 18+ check (if the account hasn't confirmed it) and "where do you sell from".
    Then: snap or pick photos (each is shrunk on the phone by btm.js and uploads right away), a name, a price (or Free /
    Make an offer), an optional note, Post. After posting: confetti and "Snap the next thing" for rapid fire.
    Server: upload_photo, create_listing, get_for_edit, update_listing (+ set_spot / confirm_age via btm.py)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.edit_key = args[0] if args else None
        self.tiles: list = []  # {id, key, src, state: "up" | "ok" | "err", full, thumb}
        self.mode = "price"
        self.posted = 0
        self.seq = 0
        self.alive = True
        self.tray.add_event_handler("x-cover", self._cover)
        self.tray.add_event_handler("x-remove", self._remove)
        self.tray.add_event_handler("x-retry", self._retry)
        self.dom_nodes["cam_input"].addEventListener("change", self._files_chosen)
        self.dom_nodes["lib_input"].addEventListener("change", self._files_chosen)
        state.set_control_attr(self.title_box, "maxlength", "80")
        state.set_control_attr(self.title_box, "autocomplete", "off")
        state.set_control_attr(self.title_box, "enterkeyhint", "done")
        state.set_control_attr(self.price_box, "aria-label", "Price in dollars")
        state.set_control_attr(self.price_box, "inputmode", "decimal")
        state.set_control_attr(self.price_box, "min", "0")
        state.set_control_attr(self.note_box, "maxlength", "1000")
        state.set_control_attr(self.note_box, "aria-label", "Note")
        state.heading(self.form_title, 1)
        self._start()

    def leave(self):
        self.alive = False

    def _me(self):
        return state.me() or {}

    # ---- which part shows
    def _parts(self, part):
        for name, el in (("setup", self.setup_part), ("form", self.form_part), ("done", self.done_part),
                         ("missing", self.missing)):
            el.visible = name == part

    def _start(self):
        m = self._me()
        if not m.get("adult") or not m.get("spot"):
            self._setup()
            return
        if not self.edit_key:
            self._draw_form()
            return
        r = anvil.server.call("get_for_edit", self.edit_key)
        if not r.get("ok"):
            self._parts("missing")
            self.missing_title.text = r.get("error") or "That item isn't yours to edit."
            return
        it = r["item"]
        self.mode = it.get("price_mode") or "price"
        self.title_box.text = it["title"]
        self.price_box.text = ("%g" % it["price"]) if it.get("price") is not None else ""
        self.note_box.text = it.get("note") or ""
        self.tiles = []
        for k in it.get("photo_keys") or []:
            self.seq += 1
            self.tiles.append({"id": "t%d" % self.seq, "key": k, "src": btm.photo(k, True), "state": "ok"})
        self._draw_form()

    # ---- before the first post: 18+ and the selling spot
    def _setup(self):
        self._parts("setup")
        m = self._me()
        adult, spot = bool(m.get("adult")), m.get("spot")
        self.age_step.classes["done"] = adult
        anvil.js.get_dom_node(self.age_num).textContent = "✓" if adult else "1"
        self.age_done.visible, self.age_button.visible = adult, not adult
        self.spot_step.classes["done"] = bool(spot)
        anvil.js.get_dom_node(self.spot_num).textContent = "✓" if spot else "2"
        self.spot_done.visible, self.spot_button.visible = bool(spot), not spot
        self.spot_done.text = spot["label"] if spot else ""
        self.spot_button.enabled = adult

    @handle("age_button", "click")
    def age_button_click(self, **event_args):
        if btm.age_gate():
            self._start()

    @handle("spot_button", "click")
    def spot_button_click(self, **event_args):
        if btm.edit_spot():
            self._start()

    @handle("change_spot", "click")
    def change_spot_click(self, **event_args):
        if btm.edit_spot():
            self.spot_label.text = "Selling from " + self._me()["spot"]["label"]

    # ---- the form
    def _draw_form(self):
        self._parts("form")
        editing = bool(self.edit_key)
        self.form_title.text = "Edit item" if editing else "Sell something"
        self.form_lead.text = ("Change anything, then save." if editing else
                               "Next one! Snap it, name it, sold." if self.posted else "Snap it. Name it. Sold.")
        self.spot_label.text = "Selling from " + self._me()["spot"]["label"]
        self.cancel_box.visible = editing
        if editing:
            state.set_attr(self.cancel_link, "href", router.href("item", self.edit_key))
        if self.note_box.text:
            self.dom_nodes["more"].setAttribute("open", "")
        else:
            self.dom_nodes["more"].removeAttribute("open")
        self._mode_draw()
        self._tray()

    def _tray(self):
        n = len(self.tiles)
        self.snap_box.visible = n == 0
        self.tray_box.visible = n > 0
        self.tray.items = [dict(t, index=i) for i, t in enumerate(self.tiles)]
        self.add_tile.visible = n < MAX
        self.cover_hint.visible = n > 1
        waiting = any(t["state"] == "up" for t in self.tiles)
        self.post_button.text = "Uploading photos…" if waiting else "Save changes" if self.edit_key else "Post it"
        self.post_button.enabled = not waiting

    def _mode_draw(self):
        for name, el in (("price", self.m_price), ("free", self.m_free), ("offer", self.m_offer)):
            el.classes["on"] = self.mode == name
        self.money_box.visible = self.quick_box.visible = self.mode == "price"

    def mode_click(self, event):
        self.mode = event.currentTarget.getAttribute("data-mode")
        self._mode_draw()
        if self.mode == "price":
            self.price_box.focus()

    def amount_click(self, event):
        self.price_box.text = str(event.currentTarget.getAttribute("data-amount"))

    def _err(self, message):
        self.error.text = message or ""
        self.error.visible = bool(message)

    # ---- photos: shrink, show, upload one by one
    def cam_click(self, event):
        self.dom_nodes["cam_input"].click()

    def lib_click(self, event):
        self.dom_nodes["lib_input"].click()

    def _files_chosen(self, event):
        inp = event.target
        files = list(window.Array["from"](getattr(inp, "files")))[:MAX - len(self.tiles)]
        inp.value = ""
        if not files:
            return
        new = []
        for f in files:
            self.seq += 1
            t = {"id": "t%d" % self.seq, "key": None, "src": "", "state": "up", "full": None, "thumb": None}
            self.tiles.append(t)
            new.append((t, f))
        self._tray()
        if not (self.title_box.text or ""):
            self.title_box.focus()
        for t, f in new:
            try:
                d = window.BTM.shrink(f)
            except Exception as e:
                self.tiles = [x for x in self.tiles if x is not t]
                self._tray()
                state.toast(_message(e, "That picture couldn't be read."), "error")
                continue
            t["full"], t["thumb"], t["src"] = d.full, d.thumb, d.thumb
            self._tray()
            self._upload(t)

    def _upload(self, t):
        if not self.alive or t not in self.tiles:
            return
        t["state"] = "up"
        self._tray()
        try:
            r = anvil.server.call_s("upload_photo", t["full"], t["thumb"])
        except Exception:
            r = {"ok": False, "error": "That photo didn't upload. Check your connection and tap it to retry."}
        if not self.alive:
            return
        if r.get("ok"):
            t["key"], t["state"], t["full"] = r["key"], "ok", None  # keep memory small
        else:
            t["state"] = "err"
            state.toast(r.get("error") or "That photo didn't upload.", "error")
        self._tray()

    def _find(self, tile_id):
        for t in self.tiles:
            if t["id"] == tile_id:
                return t
        return None

    def _cover(self, tile_id, **event_args):
        t = self._find(tile_id)
        if t is not None and self.tiles.index(t) > 0:
            self.tiles.remove(t)
            self.tiles.insert(0, t)
            self._tray()

    def _remove(self, tile_id, **event_args):
        self.tiles = [x for x in self.tiles if x["id"] != tile_id]
        self._tray()

    def _retry(self, tile_id, **event_args):
        t = self._find(tile_id)
        if t is None:
            return
        if t.get("full"):
            self._upload(t)
        else:
            self.tiles.remove(t)
            self._tray()
            state.toast("Please take that photo again.")

    # ---- post / save
    @handle("post_button", "click")
    def post_button_click(self, **event_args):
        self._err("")
        title = (self.title_box.text or "").strip()
        price_text = self.price_box.text
        if not self.tiles:
            self._err("Add at least one photo: tap the camera.")
            return
        if len(title) < 2:
            self._err('Give it a name, like "Blue armchair".')
            self.title_box.focus()
            return
        if self.mode == "price" and (price_text is None or price_text == ""):
            self._err("Type a price, or choose Free or Make an offer.")
            self.price_box.focus()
            return
        if any(t["state"] == "err" for t in self.tiles):
            self._err("Some photos didn't upload. Tap them to retry, or remove them.")
            return
        if any(t["state"] == "up" for t in self.tiles):
            self._err("Hang on: the photos are still uploading.")
            return
        keys = [t["key"] for t in self.tiles]
        price = float(price_text) if self.mode == "price" else None
        note = self.note_box.text or ""
        self.post_button.enabled = False
        try:
            if self.edit_key:
                r = anvil.server.call("update_listing", self.edit_key, title, self.mode, price, note, keys)
            else:
                r = anvil.server.call("create_listing", title, self.mode, price, note, keys)
        finally:
            self.post_button.enabled = True
        if not r.get("ok"):
            self._err(r.get("error") or "That didn't work. Please try again.")
            return
        if self.edit_key:
            state.toast("Saved.", "ok")
            router.go("item", self.edit_key)
            return
        self.posted += 1
        self._done(r["key"], title, price)

    def _done(self, key, title, price):
        me = self._me()
        it = {"key": key, "title": title, "price": price, "price_mode": self.mode, "status": "active",
              "cover": self.tiles[0]["key"], "photos": len(self.tiles), "posted": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "area": me["spot"]["label"], "mine": True, "_no_heart": True}
        self._parts("done")
        self.done_count.text = ("%d items posted this round" % self.posted) if self.posted > 1 else "Posted"
        self.done_text.text = "Neighbours near %s can see it now. Messages land in Chats." % me["spot"]["label"]
        self.done_slot.clear()
        self.done_slot.add_component(Card(item=it))
        state.set_attr(self.see_link, "href", router.href("item", key))
        btm.confetti()
        self.tiles = []
        self.mode = "offer" if self.mode == "offer" else "price"
        self.title_box.text, self.price_box.text, self.note_box.text = "", "", ""

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        self._draw_form()
        if btm.media("(pointer: coarse)"):
            self.dom_nodes["cam_input"].click()


def _message(e, fallback):
    text = str(e) or ""
    return text.split(": ", 1)[-1] if text else fallback
