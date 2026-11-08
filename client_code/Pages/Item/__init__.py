from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import ItemTemplate
from ... import btm, router, state


class Item(ItemTemplate):
    """#item/<key> (for everyone): one listing. Swipeable photos (+ thumbnails on desktop, a lightbox on click), the
    price sticker, where (area, distance, a ~1 km circle on the map), the seller, quick messages, save / share /
    report. The owner gets the controls instead: reserved / sold, bump, edit, delete, views and chats.
    Server: get_listing, start_chat, toggle_save (btm.py), report_listing, set_listing_status, bump_listing,
    delete_listing. An item that's gone shows a friendly "isn't available" state."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.key = args[0] if args else ""
        self.it: dict = {}
        self.idx = 0
        state.heading(self.title, 1)
        self.quick.add_event_handler("x-quick", self._quick)
        self.thumbs.add_event_handler("x-thumb", self._thumb)
        self.dom_nodes["strip"].addEventListener("scroll", self._scrolled)
        state.set_control_attr(self.message_box, "maxlength", "1000")
        state.set_control_attr(self.message_box, "aria-label", "Message")
        self._load()

    # ---- loading
    def _load(self):
        r = anvil.server.call("get_listing", self.key, btm.opts())
        ok = bool(r.get("ok"))
        self.missing.visible = not ok
        self.found.visible = ok
        if not ok:
            self.missing_title.text = r.get("error") or "This item isn't available any more."
            state.heading(self.missing_title, 1)
            return
        self.it = r["item"]
        self._draw()

    def _draw(self):
        it, me = self.it, state.me()
        s = it["seller"]
        first = btm.first_name(s["name"])
        owner, sold = bool(it.get("can_edit")), it["status"] == "sold"
        window.document.title = it["title"] + " · Better Than Marketplace"

        # gallery
        keys = it.get("photo_keys") or []
        self.idx = 0
        self.photos.items = [{"src": btm.photo(k), "alt": "%s (photo %d)" % (it["title"], i + 1), "lazy": i > 0}
                             for i, k in enumerate(keys)]
        many = len(keys) > 1
        self.dots.items = [{"on": i == 0} for i in range(len(keys))] if many else []
        self.thumbs.items = [{"src": btm.photo(k, True), "index": i, "on": i == 0} for i, k in enumerate(keys)] if many else []
        self.dots_box.visible = self.thumbs_box.visible = many
        self.prev_button.visible = self.next_button.visible = many
        self.sold_stamp.visible = sold

        # facts
        btm.tag(self.tag, it, "big")
        self.reserved.visible = it["status"] == "reserved"
        self.demo.visible = bool(it.get("demo"))
        self.title.text = it["title"]
        self.where.text = (it.get("area") or "") + ((" · %s away" % btm.dist(it["dist"])) if it.get("dist") is not None else "")
        self.posted.text = "Posted " + state.ago(it.get("posted"))

        # visitor actions vs. the owner's controls
        self.actions.visible = not owner
        self.save_btn.visible = not sold
        self._save_state(bool(it.get("saved")))
        state.set_attr(self.save_btn, "data-save", it["key"])
        self.report_button.visible = bool(me)
        self.owner_box.visible = owner
        if owner:
            self.hidden_note.visible = bool(it.get("hidden"))
            self.hidden_note.text = (it.get("hidden_reason") or "Hidden by a moderator.") + " Only you can see it."
            v, c = it.get("views") or 0, it.get("chats") or 0
            self.views.text = "%d %s" % (v, "view" if v == 1 else "views")
            self.chats.text = "%d %s" % (c, "chat" if c == 1 else "chats")
            for name, el in (("active", self.st_active), ("reserved", self.st_reserved), ("sold", self.st_sold)):
                el.classes["on"] = it["status"] == name
            state.set_attr(self.edit_link, "href", router.href("sell", it["key"]))
            self.bump_button.visible = not sold
            self.bump_button.enabled = bool(it.get("can_bump"))
            self.bump_button.tooltip = "" if it.get("can_bump") else "Once a day"
            self.bump_hint.visible = not sold and not it.get("can_bump")

        # asking the seller
        self.sold_box.visible = sold and not owner
        state.set_attr(self.sold_link, "href", router.href("seller", s["key"]))
        anvil.js.get_dom_node(self.sold_link).textContent = "See what else %s is selling" % first
        self.join_box.visible = not sold and not owner and not me
        self.join_text.text = "Join free to message %s (you need to be 18 or older)." % first
        self.ask_box.visible = not sold and not owner and bool(me)
        if self.ask_box.visible:
            self.ask_title.text = ("Message " if it.get("chat") else "Ask ") + first
            state.heading(self.ask_title, 2)
            self.has_chat.visible = bool(it.get("chat"))
            if it.get("chat"):
                state.set_attr(self.chat_link, "href", router.href("messages", it["chat"]))
            self.quick.items = [{"text": t} for t in self._quick_texts()]
            self.message_box.text = "" if it.get("chat") else "Hi! Is this still available?"

        # note, seller, map, safety
        self.note_box.visible = bool(it.get("note"))
        self.note_title.text = "From " + ("you" if owner else first)
        state.heading(self.note_title, 2)
        self.note.text = it.get("note") or ""
        state.set_attr(self.seller_link, "href", router.href("seller", s["key"]))
        self.seller_initials.text = state.initials(s["name"])
        self.seller_name.text = s["name"]
        self.seller_facts.text = "Member since %s · %d sold · %d for sale" % (btm.long_date(s.get("since")), s["sold"], s["active"])
        self.map_box.visible = bool(it.get("map"))
        if it.get("map"):
            self.area_map.show_area(it["map"]["lat"], it["map"]["lng"], it.get("area") or "")
            self.map_hint.text = ("Roughly where %s: exact spots are never shown. Agree on a place to meet in the chat."
                                  % ("you are" if owner else first + " is"))
        self.safe_box.visible = not owner
        more = it.get("more") or []
        self.more_box.visible = bool(more)
        self.more_title.text = "More from " + ("you" if owner else first)
        state.heading(self.more_title, 2)
        self.more.items = more

    def _quick_texts(self):
        it = self.it
        q = ["Hi! Is this still available?", "Could I pick it up today?", "Where could we meet?"]
        if it.get("price_mode") == "price" and (it.get("price") or 0) >= 10:
            q.insert(1, "Would you take %s?" % btm.money(max(1, round(it["price"] * 0.8))))
        if it.get("price_mode") == "offer":
            q.insert(1, "How much would you like for it?")
        return q

    # ---- gallery
    def _scrolled(self, event):
        strip = self.dom_nodes["strip"]
        i = int(round(strip.scrollLeft / max(1, strip.clientWidth)))
        if i == self.idx:
            return
        self.idx = i
        for j, c in enumerate(self.dots.get_components()):
            getattr(c, "set_on")(j == i)
        for j, c in enumerate(self.thumbs.get_components()):
            getattr(c, "set_on")(j == i)

    def _show(self, i):
        n = len(self.it.get("photo_keys") or [])
        if not n:
            return
        strip = self.dom_nodes["strip"]
        strip.scrollTo({"left": ((i + n) % n) * strip.clientWidth, "behavior": "smooth"})

    @handle("prev_button", "click")
    def prev_button_click(self, **event_args):
        self._show(self.idx - 1)

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        self._show(self.idx + 1)

    def _thumb(self, index, **event_args):
        self._show(index)

    # ---- visitor actions
    @handle("back_button", "click")
    def back_button_click(self, **event_args):
        if window.history.length > 1:
            window.history.back()
        else:
            router.go("browse")

    def _save_state(self, saved):
        self.save_btn.classes["on"] = saved
        state.set_attr(self.save_btn, "aria-pressed", "true" if saved else "false")
        label = anvil.js.get_dom_node(self.save_btn).querySelector("[data-save-label]")
        if label is not None:
            label.textContent = "Saved" if saved else "Save"

    def save_click(self, event):
        saved = btm.toggle_save(self.it["key"])
        if saved is not None:
            self.it["saved"] = saved

    @handle("share_button", "click")
    def share_button_click(self, **event_args):
        btm.share(self.it)

    @handle("owner_share", "click")
    def owner_share_click(self, **event_args):
        btm.share(self.it)

    @handle("report_button", "click")
    def report_button_click(self, **event_args):
        from ...Dialogs.Report import Report
        if alert(Report(self.it["key"]), buttons=[], role="app-dialog", dismissible=True):
            state.toast("Thanks. We'll take a look.", "ok")

    @handle("join_button", "click")
    def join_button_click(self, **event_args):
        router.remember_after(router.href("item", self.key))
        router.go("auth", "signup")

    def signin_click(self, event):
        event.preventDefault()
        router.remember_after(router.href("item", self.key))
        router.go("auth")

    def _quick(self, text, **event_args):
        self.message_box.text = text
        self.message_box.focus()

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        text = (self.message_box.text or "").strip()
        if not text:
            self.message_box.focus()
            return
        me = state.me() or {}
        if not me.get("adult") and not btm.age_gate():
            return
        self.send_button.enabled = False
        try:
            r = state.call("start_chat", self.key, text)
        finally:
            self.send_button.enabled = True
        if r is None:
            return
        state.toast("Sent to %s." % btm.first_name(self.it["seller"]["name"]), "ok")
        router.go("messages", r["chat"])

    # ---- the owner's controls
    def status_click(self, event):
        status = event.currentTarget.getAttribute("data-status")
        if status == self.it["status"]:
            return
        if state.call("set_listing_status", self.key, status) is None:
            return
        if status == "sold":
            btm.confetti()
            state.toast("Sold! Nice one.", "ok")
        else:
            state.toast("Marked as reserved." if status == "reserved" else "Back on sale.", "ok")
        self._load()

    @handle("bump_button", "click")
    def bump_button_click(self, **event_args):
        if state.call("bump_listing", self.key) is not None:
            state.toast("Bumped to the top of the feed.", "ok")
            self._load()

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if not confirm("The photos are deleted too. Chats about it stay, with its name.",
                       title='Delete "%s"?' % self.it["title"], buttons=[("Cancel", False), ("Delete", True)],
                       role="app-dialog"):
            return
        if state.call("delete_listing", self.key) is not None:
            state.toast("Deleted.")
            router.go("mine" if state.me() else "browse")
