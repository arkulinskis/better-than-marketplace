from anvil import *
import anvil.js

from ._anvil_designer import AdminListingTemplate
from ... import btm, router, state


class AdminListing(AdminListingTemplate):
    """Admin → Listings (and inside Admin → Reports): one listing with its owner, facts and moderation buttons.
    item = an Admin._admin_card dict. In a report, item also has "_report_id" (+ "_report_open") and the buttons are
    It's fine / Hide it / Delete it (admin_resolve_report). After a change: item["_on_change"]() if given, else
    x-changed on the panel."""

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
        self.status.text = it.get("status") or ""
        state.set_attr(self.owner_link, "href", router.href("seller", it.get("owner_key") or ""))
        anvil.js.get_dom_node(self.owner_link).textContent = it.get("owner") or ""
        self.owner_email.text = (" · " + it["owner_email"]) if it.get("owner_email") else ""
        self.area.text = it.get("area") or ""
        self.when.text = state.ago(it.get("posted"))
        self.views.text = "%d views" % (it.get("views") or 0)
        self.reports.visible = bool(it.get("reports"))
        self.reports.text = state.plural(it.get("reports") or 0, "report")
        self.hidden.visible = bool(it.get("hidden"))
        self.demo.visible = bool(it.get("demo"))
        self.why.visible = bool(it.get("hidden") and it.get("hidden_reason"))
        self.why.text = it.get("hidden_reason") or ""
        in_report = "_report_id" in it
        self.box.classes["in-report"] = in_report
        self.list_acts.visible = not in_report
        self.report_acts.visible = in_report and bool(it.get("_report_open"))
        self.hide_button.visible = not it.get("hidden")
        self.show_button.visible = bool(it.get("hidden"))

    def _changed(self):
        cb = self.item.get("_on_change")
        if cb:
            cb()
        else:
            self.parent.raise_event("x-changed")

    def _hide(self, flag):
        if state.call("admin_set_hidden", self.item["key"], flag, "Hidden by a moderator." if flag else "") is not None:
            state.toast("Hidden." if flag else "Visible again.", "ok")
            self._changed()

    @handle("hide_button", "click")
    def hide_button_click(self, **event_args):
        self._hide(True)

    @handle("show_button", "click")
    def show_button_click(self, **event_args):
        self._hide(False)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("Its photos go too. This can't be undone.", title="Delete this listing?",
                   buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_listing", self.item["key"]) is not None:
                state.toast("Deleted.")
                self._changed()

    def _resolve(self, action):
        if state.call("admin_resolve_report", self.item["_report_id"], action) is not None:
            state.toast("Done.", "ok")
            self._changed()

    @handle("fine_button", "click")
    def fine_button_click(self, **event_args):
        self._resolve("dismiss")

    @handle("hide_it_button", "click")
    def hide_it_button_click(self, **event_args):
        self._resolve("hide")

    @handle("delete_it_button", "click")
    def delete_it_button_click(self, **event_args):
        if confirm("Delete the item?", buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            self._resolve("delete")
