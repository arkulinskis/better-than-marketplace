from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import MessagesTemplate
from ... import btm, router, state
from ...Dialogs.PickupPlan import PickupPlan

FILTERS = [("all", "All"), ("buying", "Buying"), ("selling", "Selling")]
BUYER_QUICK = ["Is it still available?", "Could I pick it up today?", "Where could we meet?", "Thanks!"]
PLAN_BUTTONS = ("plan_new", "plan_confirm", "plan_onway", "plan_late", "plan_met", "plan_noshow", "plan_change", "plan_cancel")
SOON_MS = 3 * 3600 * 1000  # "On my way" / "Running late" show from 3 hours before the pickup
SELLER_QUICK = ["Yes, it's still available!", "When would suit you?", "Sorry, it's reserved.", "Thanks!"]


class Messages(MessagesTemplate):
    """#messages[/<chatKey>] (members): chats between buyers and sellers. The list (All / Buying / Selling) and, when
    a chat is open, the thread beside it (on phones: the thread alone). The open thread checks for new messages every
    4 seconds, quietly (poll_chat); leave() stops it. Quick replies for the common questions; Enter sends on desktop.
    The pickup plan card above the thread (2026-11-20): plan a time + public place (Dialogs/PickupPlan, with safe spots
    nearby), confirm, On my way / Running late / Can't make it, then "We met" / "They didn't show" (the pickup record).
    Server: list_chats, get_chat, send_message, poll_chat, propose_pickup, answer_pickup, mark_pickup."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.key = args[0] if args else None
        self.filter = state.store_get("chatFilter", "all") or "all"
        self.all_chats: list = []
        self.chat: dict = {}
        self.msgs: list = []
        self.plan = None
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
                self.plan = r.get("plan")
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
        self._plan_draw()
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
            if m.get("kind") == "auto":
                out.append({"kind": "note", "text": m["text"]})
                continue
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
            plan = r.get("plan")
            if plan != self.plan:
                self.plan = plan
                self._plan_draw()

    # ---- the pickup plan card
    def _day_text(self, d):
        today = window.Date()
        tomorrow = window.Date()
        tomorrow.setDate(today.getDate() + 1)
        day = ("Today" if d.toDateString() == today.toDateString() else
               "Tomorrow" if d.toDateString() == tomorrow.toDateString() else
               d.toLocaleDateString([], {"weekday": "short", "day": "numeric", "month": "short"}))
        return "%s, %s" % (day, d.toLocaleTimeString([], {"hour": "numeric", "minute": "2-digit"}))

    def _plan_draw(self):
        c, p = self.chat, self.plan
        live = c.get("status") in ("active", "reserved")
        show = {name: False for name in PLAN_BUTTONS}
        status = p.get("status") if p else None
        visible = live or (status == "confirmed")
        self.plan_box.visible = visible
        if not visible:
            return
        other = btm.first_name(c.get("other")) or "They"
        badge, tone, hint = "", "", ""
        if not p:
            self.plan_when.text = "No pickup time yet"
            self.plan_place.text = "Agree on a day, a time and a public place."
            self.plan_new.text = "Plan pickup"
            show["plan_new"] = True
        else:
            d = window.Date(p["at"])
            self.plan_when.text = self._day_text(d)
            self.plan_place.text = "at " + (p.get("place") or "")
            if status == "proposed":
                badge, tone = "Waiting", "badge-warn"
                if p.get("mine"):
                    hint = "Waiting for %s to confirm." % other
                    self.plan_change.text, self.plan_cancel.text = "Change", "Take it back"
                    show["plan_change"] = show["plan_cancel"] = live
                else:
                    hint = "%s suggested this. Does it work for you?" % other
                    self.plan_change.text = "Suggest another"
                    show["plan_confirm"] = show["plan_change"] = live
            elif p.get("my_mark"):
                badge, tone = "Done", "badge-good"
                hint = ("Thanks! You said you met." if p["my_mark"] == "met" else
                        "Thanks for telling us. It counts in %s's pickup record." % other)
                self.plan_new.text = "Plan another"
                show["plan_new"] = live
            elif p.get("can_mark"):
                badge, tone = "Confirmed", "badge-good"
                hint = "How did it go? Your answer builds %s's pickup record." % other
                show["plan_met"] = show["plan_noshow"] = True
                show["plan_onway"] = show["plan_late"] = live and window.Date.now() < d.getTime() + 3600 * 1000
            else:
                badge, tone = "Confirmed", "badge-good"
                hint = "You both agreed. Tap below if plans change."
                soon = d.getTime() - window.Date.now() < SOON_MS
                show["plan_onway"] = show["plan_late"] = live and soon
                self.plan_cancel.text = "Can't make it"
                show["plan_cancel"] = live
        self.plan_badge.visible = bool(badge)
        self.plan_badge.text = badge
        self.plan_badge.role = ["badge", tone] if tone else ["badge"]
        self.plan_hint.text = hint
        self.plan_hint.visible = bool(hint)
        for name, on in show.items():
            getattr(self, name).visible = on
        self.plan_acts.visible = any(show.values())

    def _plan_reply(self, r):
        if r is None:
            return
        self.plan = r.get("plan")
        if r.get("message"):
            self._append([r["message"]])
        self._plan_draw()

    def _adult(self):
        me = state.me() or {}
        return bool(me.get("adult")) or bool(btm.age_gate())

    def _open_plan_dialog(self, place=""):
        if not self._adult():
            return
        c = self.chat
        got = alert(PickupPlan(other=btm.first_name(c.get("other")), spot=c.get("spot"), place=place),
                    buttons=[], role="app-dialog", dismissible=True)
        if not got:
            return
        self._plan_reply(state.call("propose_pickup", self.key, got["at"], got["place"], got.get("lat"), got.get("lng"),
                                    got.get("label") or ""))

    @handle("plan_new", "click")
    def plan_new_click(self, **event_args):
        self._open_plan_dialog()

    @handle("plan_change", "click")
    def plan_change_click(self, **event_args):
        self._open_plan_dialog((self.plan or {}).get("place") or "")

    def _answer(self, action):
        if not self._adult():
            return
        self._plan_reply(state.call("answer_pickup", self.key, action))

    @handle("plan_confirm", "click")
    def plan_confirm_click(self, **event_args):
        self._answer("confirm")

    @handle("plan_onway", "click")
    def plan_onway_click(self, **event_args):
        self._answer("on_way")

    @handle("plan_late", "click")
    def plan_late_click(self, **event_args):
        self._answer("late")

    @handle("plan_cancel", "click")
    def plan_cancel_click(self, **event_args):
        p = self.plan or {}
        question = ("Take back your pickup plan?" if p.get("status") == "proposed" and p.get("mine") else
                    "Tell %s you can't make it?" % (btm.first_name(self.chat.get("other")) or "them"))
        if confirm(question, buttons=[("Keep it", False), ("Yes", True)]):
            self._answer("cancel")

    @handle("plan_met", "click")
    def plan_met_click(self, **event_args):
        r = state.call("mark_pickup", self.key, True)
        if r is None:
            return
        self._plan_reply(r)
        c = self.chat
        if c.get("role") == "selling" and c.get("listing") and c.get("status") in ("active", "reserved"):
            if confirm("Nice! Mark \u201c%s\u201d as sold?" % (c.get("title") or "the item"),
                       buttons=[("Not yet", False), ("Mark sold", True)]):
                if state.call("set_listing_status", c["listing"], "sold") is not None:
                    c["status"] = "sold"
                    btm.tag(self.tag, c, "inline")
                    self._plan_draw()
                    self._bubbles()
                    state.toast("Marked as sold. Congrats!", "ok")

    @handle("plan_noshow", "click")
    def plan_noshow_click(self, **event_args):
        other = btm.first_name(self.chat.get("other")) or "they"
        if confirm("Say %s didn't show up? It counts in their pickup record." % other,
                   buttons=[("Cancel", False), ("They didn't show", True)]):
            self._plan_reply(state.call("mark_pickup", self.key, False))

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
