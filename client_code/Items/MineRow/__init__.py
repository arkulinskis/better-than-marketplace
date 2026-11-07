from anvil import *
import anvil.js

from ._anvil_designer import MineRowTemplate
from ... import btm, router, state


class MineRow(MineRowTemplate):
    """One of your listings on My stuff: photo, name, price sticker, views, chats, age, and the quick actions for its
    status. Every action raises x-changed on the panel so the page reloads the counts."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        href = router.href("item", it["key"])
        state.set_attr(self.pic_link, "href", href)
        state.set_attr(self.title_link, "href", href)
        anvil.js.get_dom_node(self.title_link).textContent = it["title"]
        img = self.dom_nodes["img"]
        if it.get("cover"):
            img.src = btm.photo(it["cover"], True)
        else:
            img.style.display = "none"
        self.ph.visible = not it.get("cover")
        btm.tag(self.tag, it, "inline")
        self.views.text = "%d views" % (it.get("views") or 0)
        self.chats.text = state.plural(it.get("chats") or 0, "chat")
        sold = it["status"] == "sold"
        self.when.text = ("sold " + state.ago(it["sold_at"])) if sold and it.get("sold_at") else state.ago(it.get("posted"))
        self.hidden.visible = bool(it.get("hidden_reason"))
        self.reserve_button.visible = it["status"] == "active"
        self.unreserve_button.visible = it["status"] == "reserved"
        self.sold_button.visible = it["status"] in ("active", "reserved")
        self.again_button.visible = sold
        self.bump_button.visible = not sold and bool(it.get("can_bump"))
        state.set_attr(self.edit_link, "href", router.href("sell", it["key"]))
        state.set_attr(self.edit_link, "aria-label", "Edit " + it["title"])
        state.set_control_attr(self.delete_button, "aria-label", "Delete " + it["title"])

    def _set(self, status):
        if state.call("set_listing_status", self.item["key"], status) is None:
            return
        if status == "sold":
            btm.confetti()
            state.toast("Sold! Nice one.", "ok")
        else:
            state.toast("Marked as reserved." if status == "reserved" else "Back on sale.", "ok")
        self.parent.raise_event("x-changed")

    @handle("reserve_button", "click")
    def reserve_button_click(self, **event_args):
        self._set("reserved")

    @handle("unreserve_button", "click")
    def unreserve_button_click(self, **event_args):
        self._set("active")

    @handle("again_button", "click")
    def again_button_click(self, **event_args):
        self._set("active")

    @handle("sold_button", "click")
    def sold_button_click(self, **event_args):
        self._set("sold")

    @handle("bump_button", "click")
    def bump_button_click(self, **event_args):
        if state.call("bump_listing", self.item["key"]) is not None:
            state.toast("Bumped to the top.", "ok")
            self.parent.raise_event("x-changed")

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if not confirm("Its photos are deleted too. This can't be undone.", title="Delete this item?",
                       buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            return
        if state.call("delete_listing", self.item["key"]) is not None:
            state.toast("Deleted.")
            self.parent.raise_event("x-changed")
