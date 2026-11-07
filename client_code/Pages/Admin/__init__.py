from anvil import *

from ._anvil_designer import AdminTemplate
from ... import state

TABS = ["overview", "listings", "reports", "feedback", "users", "demo"]


class Admin(AdminTemplate):
    """#admin/<tab> (admins): overview numbers, every listing (hide / show / delete), reports from members (it's fine /
    hide it / delete it), the old feedback inbox, users (admin / active switches) and the demo data.
    Each tab is its own address, so the browser's back button works."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = args[0] if args and args[0] in TABS else "overview"
        self._filter = "new"
        self._which = "all"
        self._rstatus = "open"
        parts = {"overview": self.overview_part, "listings": self.listings_part, "reports": self.reports_part,
                 "feedback": self.feedback_part, "users": self.users_part, "demo": self.demo_part}
        tabs = {"overview": self.tab_overview, "listings": self.tab_listings, "reports": self.tab_reports,
                "feedback": self.tab_feedback, "users": self.tab_users, "demo": self.tab_demo}
        for name in TABS:
            parts[name].visible = name == self.tab
            tabs[name].classes["on"] = name == self.tab
            state.set_attr(tabs[name], "aria-current", "page" if name == self.tab else None)
        self.feedback_panel.add_event_handler("x-changed", self._feedback_changed)
        self.listings_panel.add_event_handler("x-changed", self._listings_changed)
        self.reports_panel.add_event_handler("x-changed", self._reports_changed)
        getattr(self, "_" + self.tab)()

    def _seg(self, buttons, current):
        for key, el in buttons:
            on = key == current
            el.role = ["seg", "on"] if on else ["seg"]
            state.set_control_attr(el, "aria-pressed", "true" if on else "false")

    # ---- overview
    def _overview(self):
        d = state.call("admin_overview")
        for label, key in ((self.s_users, "users"), (self.s_listings, "listings"), (self.s_sold, "sold"),
                           (self.s_chats, "chats"), (self.s_reports, "reports_open"), (self.s_hidden, "hidden"),
                           (self.s_feedback, "feedback_new"), (self.s_admins, "admins")):
            label.text = str(d.get(key) or 0)
        self.s_admins_label.text = "admin" if d["admins"] == 1 else "admins"
        self.demo_line.text = "Demo data is %s (%d demo people). Manage it in the Demo data tab." % (
            d["demo"]["state"], d["demo"]["counts"].get("users", 0))

    # ---- listings
    def _listings(self):
        d = state.call("admin_listings", (self.ls_box.text or "").strip() or None, self._which)
        if d is None:
            return
        self.listings_panel.items = d["items"]
        self.no_listings.visible = not d["items"]
        self.ls_count.text = state.plural(d["total"], "listing")
        self._seg((("all", self.w_all), ("reported", self.w_reported), ("hidden", self.w_hidden), ("sold", self.w_sold)),
                  self._which)

    def _set_which(self, value):
        self._which = value
        self._listings()

    @handle("w_all", "click")
    def w_all_click(self, **event_args):
        self._set_which("all")

    @handle("w_reported", "click")
    def w_reported_click(self, **event_args):
        self._set_which("reported")

    @handle("w_hidden", "click")
    def w_hidden_click(self, **event_args):
        self._set_which("hidden")

    @handle("w_sold", "click")
    def w_sold_click(self, **event_args):
        self._set_which("sold")

    @handle("ls_box", "pressed_enter")
    def ls_box_pressed_enter(self, **event_args):
        self._listings()

    @handle("ls_button", "click")
    def ls_button_click(self, **event_args):
        self._listings()

    def _listings_changed(self, **event_args):
        self._listings()

    # ---- reports
    def _reports(self):
        d = state.call("admin_reports", self._rstatus)
        if d is None:
            return
        self.reports_panel.items = d["reports"]
        self.no_reports.visible = not d["reports"]
        self.no_reports_title.text = "No open reports" if self._rstatus == "open" else "No reports"
        self.r_open.text = "Open (%d)" % (d.get("open") or 0)
        self._seg((("open", self.r_open), ("done", self.r_done), ("dismissed", self.r_dismissed)), self._rstatus)

    def _set_rstatus(self, value):
        self._rstatus = value
        self._reports()

    @handle("r_open", "click")
    def r_open_click(self, **event_args):
        self._set_rstatus("open")

    @handle("r_done", "click")
    def r_done_click(self, **event_args):
        self._set_rstatus("done")

    @handle("r_dismissed", "click")
    def r_dismissed_click(self, **event_args):
        self._set_rstatus("dismissed")

    def _reports_changed(self, **event_args):
        self._reports()

    # ---- feedback
    def _feedback(self):
        d = state.call("list_feedback", None)
        items = [i for i in d["items"] if self._filter == "all" or i["status"] == self._filter]
        self.feedback_panel.items = items
        self.no_feedback.visible = not items
        labels = {"new": "New", "read": "Read", "done": "Done", "all": "All"}
        buttons = (("new", self.f_new), ("read", self.f_read), ("done", self.f_done), ("all", self.f_all))
        for key, el in buttons:
            n = len(d["items"]) if key == "all" else d["counts"].get(key, 0)
            el.text = "%s (%d)" % (labels[key], n)
        self._seg(buttons, self._filter)

    def _set_filter(self, value):
        self._filter = value
        self._feedback()

    @handle("f_new", "click")
    def f_new_click(self, **event_args):
        self._set_filter("new")

    @handle("f_read", "click")
    def f_read_click(self, **event_args):
        self._set_filter("read")

    @handle("f_done", "click")
    def f_done_click(self, **event_args):
        self._set_filter("done")

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._set_filter("all")

    def _feedback_changed(self, **event_args):
        self._feedback()

    # ---- users
    def _users(self, query=None):
        d = state.call("list_users", query or None)
        self.users_panel.items = d["users"]
        self.users_count.text = state.plural(d["total"], "person", "people")

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self._users(self.search_box.text)

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        self._users(self.search_box.text)

    # ---- demo data
    def _demo(self):
        d = state.call("admin_overview")["demo"]
        counts = ", ".join("%s %s" % (v, k) for k, v in d["counts"].items())
        self.demo_status.text = "Status: %s · %s" % (d["state"], counts)
        self.demo_load_button.text = "Reload demo data" if d["state"] == "loaded" else "Load demo data"

    @handle("demo_load_button", "click")
    def demo_load_button_click(self, **event_args):
        if confirm("Demo people and content are added (any old demo rows are replaced).", title="Load the demo data?",
                   buttons=[("Cancel", False), ("Load", True)], role="app-dialog"):
            if state.call("demo_load") is not None:
                state.toast("Done", "ok")
                self._demo()

    @handle("demo_remove_button", "click")
    def demo_remove_button_click(self, **event_args):
        if confirm("Every demo row is deleted. Real data stays.", title="Remove the demo data?",
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("demo_remove") is not None:
                state.toast("Done", "ok")
                self._demo()
