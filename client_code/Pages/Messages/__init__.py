from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import MessagesTemplate
from ... import btm, router, state

FILTERS = [("all", "All"), ("buying", "Buying"), ("selling", "Selling")]
BUYER_QUICK = ["Is it still available?", "Could I pick it up today?", "Where could we meet?", "Thanks!"]
SELLER_QUICK = ["Yes, it's still available!", "When would suit you?", "Sorry, it's reserved.", "Thanks!"]


class Messages(MessagesTemplate):
    """#messages[/<chatKey>] (members): chats between buyers and sellers. The list (All / Buying / Selling) and, when
    a chat is open, the thread beside it (on phones: the thread alone). The open thread checks for new messages every
    4 seconds, quietly (poll_chat); leave() stops it. Quick replies for the common questions; Enter sends on desktop.
    Server: list_chats, get_chat, send_message, poll_chat."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.key = args[0] if args else None
        self.filter = state.store_get("chatFilter", "all") or "all"
        self.all_chats: list = []
        self.chat: dict = {}
        self.msgs: list = []
        self.timer = None
        self.alive = True
        self.quick.add_event_handler("x-quick", self._quick)
        state.set_control_attr(self.message_box, "maxlength", "1000")
        state.set_control_attr(self.message_box, "aria-label", "Message")
        state.set_control_attr(self.message_box, "rows", "1")
        box = state.control(self.message_box)
        box.addEventListener("keydown", self._key)
        box.addEventListener("input", self._grow)
        self._load()

    def leave(self):
        self.alive = False
        if self.timer is not None:
            window.clearInterval(self.timer)
            self.timer = None

    # ---- loading
    def _load(self):
        d = state.call("list_chats")
        self.all_chats = list(d["chats"]) if d else []
        self.chat, self.msgs = {}, []
        if self.key:
            r = anvil.server.call("get_chat", self.key)
            if r.get("ok"):
                self.chat, self.msgs = r["chat"], list(r["messages"])
                for c in self.all_chats:
                    if c["key"] == self.key:
                        c["unread"] = 0
                shell = getattr(self, "layout", None)
                if shell is not None and hasattr(shell, "set_unread"):
                    shell.set_unread(sum((c.get("unread") or 0) for c in self.all_chats))
                self.timer = window.setInterval(self._poll, 4000)
            else:
                state.toast(r.get("error") or "That chat doesn't exist.", "error")
        self._draw()

    def _draw(self):
        has = bool(self.chat)
        self.wrap.classes["has-thread"] = has
        self.page_head.visible = not has
        self.grid.classes["has-thread"] = has
        self.grid.classes["single"] = not self.all_chats
        self.pane.visible = bool(self.all_chats)
        self._side()
        self.pick_hint.visible = not has
        self.thread.visible = has
        if has:
            self._thread()

    def _side(self):
        def count(r):
            return len([c for c in self.all_chats if r == "all" or c.get("role") == r])
        for (key, label), b in zip(FILTERS, [self.f_all, self.f_buying, self.f_selling]):
            b.text = "%s (%d)" % (label, count(key))
            b.role = ["seg", "on"] if self.filter == key else ["seg"]
            state.set_control_attr(b, "aria-pressed", "true" if self.filter == key else "false")
        shown = [dict(c, on=c["key"] == self.key) for c in self.all_chats if self.filter == "all" or c.get("role") == self.filter]
        self.chats.items = shown
        self.chats.visible = bool(shown)
        self.empty.visible = not shown
        self.empty_text.text = ("When someone asks about your stuff, it shows up here." if self.filter == "selling"
                                else "Found something you like? Message the seller from its page.")

    def _thread(self):
        c = self.chat
        cover = self.dom_nodes["cover"]
        if c.get("cover"):
            cover.src = btm.photo(c["cover"], True)
            cover.style.display = ""
        else:
            cover.style.display = "none"
        self.title_link.visible = bool(c.get("listing"))
        self.title_plain.visible = not c.get("listing")
        if c.get("listing"):
            state.set_attr(self.title_link, "href", router.href("item", c["listing"]))
        anvil.js.get_dom_node(self.title_link).textContent = c.get("title") or ""
        anvil.js.get_dom_node(self.title_plain).textContent = c.get("title") or ""
        self.role_text.text = "Buying from" if c.get("role") == "buying" else "Selling to"
        state.set_attr(self.other_link, "href", router.href("seller", c.get("other_key") or ""))
        anvil.js.get_dom_node(self.other_link).textContent = c.get("other") or ""
        self.tag.visible = c.get("status") != "gone"
        if c.get("status") != "gone":
            btm.tag(self.tag, c, "inline")
        self.quick.items = [{"text": t} for t in (BUYER_QUICK if c.get("role") == "buying" else SELLER_QUICK)]
        self.message_box.placeholder = "Message %s…" % btm.first_name(c.get("other"))
        self._bubbles()
        if btm.media("(pointer: fine)"):
            self.message_box.focus()

    def _bubbles(self):
        out, last_day = [], None
        today = window.Date().toDateString()
        for m in self.msgs:
            d = window.Date(m["at"])
            day = d.toDateString()
            if day != last_day:
                out.append({"kind": "day", "text": "Today" if day == today else
                            d.toLocaleDateString([], {"weekday": "short", "day": "numeric", "month": "short"})})
                last_day = day
            out.append({"kind": "msg", "text": m["text"], "mine": bool(m.get("mine")),
                        "time": d.toLocaleTimeString([], {"hour": "2-digit", "minute": "2-digit"})})
        if self.chat.get("status") == "sold":
            out.append({"kind": "note", "text": "✓ This item is marked as sold."})
        if self.chat.get("status") == "gone":
            out.append({"kind": "note", "text": "The seller took this item down."})
        self.bubbles.items = out
        body = self.dom_nodes["body"]
        body.scrollTop = body.scrollHeight

    def _append(self, fresh):
        seen = {m["id"] for m in self.msgs}
        new = [m for m in fresh if m["id"] not in seen]
        if new:
            self.msgs = self.msgs + new
            self._bubbles()

    def _poll(self, *args):
        if not self.alive or not self.chat or window.document.hidden:
            return
        after = self.msgs[-1]["at"] if self.msgs else None
        try:
            r = anvil.server.call_s("poll_chat", self.key, after)
        except Exception:
            return
        if self.alive and isinstance(r, dict) and r.get("ok"):
            self._append(list(r["messages"]))

    # ---- filter, quick replies, sending
    def _set_filter(self, value):
        self.filter = value
        state.store_set("chatFilter", value)
        self._side()

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._set_filter("all")

    @handle("f_buying", "click")
    def f_buying_click(self, **event_args):
        self._set_filter("buying")

    @handle("f_selling", "click")
    def f_selling_click(self, **event_args):
        self._set_filter("selling")

    def _quick(self, text, **event_args):
        self.message_box.text = text
        self.message_box.focus()

    def _key(self, event):
        if getattr(event, "key", None) == "Enter" and not getattr(event, "shiftKey", False) and btm.media("(pointer: fine)"):
            event.preventDefault()
            self.send_button_click()

    def _grow(self, event):
        box = event.target
        box.style.height = "auto"
        box.style.height = "%dpx" % min(140, box.scrollHeight + 4)

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        text = (self.message_box.text or "").strip()
        if not text:
            return
        me = state.me() or {}
        if not me.get("adult") and not btm.age_gate():
            return
        self.send_button.enabled = False
        try:
            r = state.call("send_message", self.key, text)
        finally:
            self.send_button.enabled = True
        if r is None:
            return
        self.message_box.text = ""
        state.control(self.message_box).style.height = ""
        self._append([r["message"]])
        for c in self.all_chats:
            if c["key"] == self.key:
                c["last_text"], c["last_mine"], c["last_at"] = text, True, r["message"]["at"]
        self.message_box.focus()
