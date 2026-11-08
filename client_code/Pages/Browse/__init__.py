from anvil import *

from ._anvil_designer import BrowseTemplate
from ... import btm, router, state

FILTERS = ["all", "free", "under20", "today"]
RADII = [(1, "Within 1 km"), (3, "Within 3 km"), (5, "Within 5 km"), (10, "Within 10 km"), (25, "Within 25 km"),
         (0, "Any distance")]
SORTS = [("near", "Nearest first"), ("new", "Newest first"), ("cheap", "Cheapest first")]


class Browse(BrowseTemplate):
    """#browse[/words] (Operate, for everyone): the feed. Nearest first when we know where you are (your selling spot,
    or a spot picked in this browser), newest first otherwise. Filters: free, under $20, today; distance; sort;
    search. The choices are remembered in this browser (store key "browse", same as the old app)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        saved = state.store_get("browse", None) or {}
        radius = saved.get("radius")
        self.st: dict = {"filter": saved.get("filter") or "all", "sort": saved.get("sort") or "near",
                         "radius": radius if radius is not None else 10, "q": args[0] if args else ""}
        self.items: list = []
        self.next = None
        me = state.me()
        self.title_member.visible = bool(me)
        self.title_guest.visible = not me
        self.join_box.visible = not me
        self.search_box.text = self.st["q"]
        state.set_control_attr(self.search_box, "type", "search")
        state.set_control_attr(self.search_box, "aria-label", "Search")
        self._head()
        self._load()

    # ---- drawing
    def _head(self):
        w = btm.where()
        self.lead.text = ("Near %s, closest first." % w["label"]) if w else "Fresh finds from your neighbours, newest first."
        self.where_button.text = w["label"] if w else "Set your spot for distances"
        state.set_control_attr(self.where_button, "aria-label", "Where distances are measured from: " + self.where_button.text)

    def _chips(self, d):
        w = btm.where()
        for key, b in zip(FILTERS, [self.f_all, self.f_free, self.f_under20, self.f_today]):
            on = self.st["filter"] == key
            b.role = ["chip", "on"] if on else ["chip"]
            state.set_control_attr(b, "aria-pressed", "true" if on else "false")
        self.radius_box.visible = bool(w)
        self.radius_box.items = [(label, r) for r, label in RADII]
        r = int(self.st["radius"] or 0)
        self.radius_box.selected_value = r if r in [x for x, _ in RADII] else 10
        state.set_control_attr(self.radius_box, "aria-label", "Distance")
        self.sort_box.items = [(label, s) for s, label in SORTS if w or s != "near"]
        self.sort_box.selected_value = d.get("sort") or self.st["sort"]
        state.set_control_attr(self.sort_box, "aria-label", "Sort")
        self.count.text = state.plural(d.get("total") or 0, "item")

    def _results(self):
        st = self.st
        self.results.items = self.items
        self.results.visible = bool(self.items)
        self.more_box.visible = bool(self.items) and self.next is not None
        self.empty.visible = not self.items
        if not self.items:
            w = btm.where()
            narrow = bool(w) and 0 < int(st["radius"] or 0) < 25
            self.empty_title.text = ('Nothing matches "%s"' % st["q"]) if st["q"] else "Nothing here yet"
            self.empty_text.text = (("Nothing within %s km. Try a wider area." % st["radius"]) if narrow
                                    else "Try another filter." if st["filter"] != "all"
                                    else "Be the first to sell something around here.")
            self.widen_button.visible = narrow
            self.clear_button.visible = bool(st["q"]) or st["filter"] != "all"

    def _opts(self, offset=0):
        return btm.opts(q=self.st["q"], filter=self.st["filter"], sort=self.st["sort"],
                        radius=int(self.st["radius"] or 0) if btm.where() else 0, offset=offset, limit=24)

    def _load(self):
        state.store_set("browse", {"filter": self.st["filter"], "sort": self.st["sort"], "radius": self.st["radius"]})
        d = state.call("browse", self._opts())
        if d is None:
            return
        self.items, self.next = list(d["items"]), d.get("next")
        self._chips(d)
        self._results()

    # ---- filters, sort, distance
    def _filter(self, key):
        self.st["filter"] = key
        self._load()

    @handle("f_all", "click")
    def f_all_click(self, **event_args):
        self._filter("all")

    @handle("f_free", "click")
    def f_free_click(self, **event_args):
        self._filter("free")

    @handle("f_under20", "click")
    def f_under20_click(self, **event_args):
        self._filter("under20")

    @handle("f_today", "click")
    def f_today_click(self, **event_args):
        self._filter("today")

    @handle("radius_box", "change")
    def radius_box_change(self, **event_args):
        self.st["radius"] = self.radius_box.selected_value
        self._load()

    @handle("sort_box", "change")
    def sort_box_change(self, **event_args):
        self.st["sort"] = self.sort_box.selected_value
        self._load()

    @handle("widen_button", "click")
    def widen_button_click(self, **event_args):
        self.st["radius"] = 25
        self._load()

    @handle("clear_button", "click")
    def clear_button_click(self, **event_args):
        self.st["q"], self.st["filter"] = "", "all"
        self.search_box.text = ""
        router.replace("browse")
        self._load()

    # ---- search
    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self.search_button_click()

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        self.st["q"] = (self.search_box.text or "").strip()
        router.replace("browse", self.st["q"])
        self._load()

    @handle("more_button", "click")
    def more_button_click(self, **event_args):
        if self.next is None:
            return
        self.more_button.enabled = False
        try:
            d = state.call("browse", self._opts(self.next))
        finally:
            self.more_button.enabled = True
        if d is None:
            return
        self.items = self.items + list(d["items"])
        self.next = d.get("next")
        self._results()

    # ---- where distances are measured from
    @handle("where_button", "click")
    def where_button_click(self, **event_args):
        w = btm.where() or {}
        me = state.me()
        extra = []
        if me and me.get("spot") and not w.get("mine"):
            extra.append(("mine", "My selling spot"))
        if w:
            extra.append(("clear", "Anywhere"))
        p = btm.pick_spot(title="Show me what's near…", ok="Show what's near here", require_label=False,
                          label_title="Name of the area (optional)",
                          text="We use this only in this browser, to sort by distance. It isn't saved with your account.",
                          label=w.get("label"), lat=w.get("lat"), lng=w.get("lng"), extra=extra)
        if not p:
            return
        if p.get("extra") == "mine":
            btm.set_where(None)
        elif p.get("extra") == "clear":
            btm.set_where("anywhere")
            self.st["sort"] = "new"
        else:
            btm.set_where(p)
            self.st["sort"] = "near"
        self._head()
        self._load()
