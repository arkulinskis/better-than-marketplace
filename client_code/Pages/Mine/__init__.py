from anvil import *

from ._anvil_designer import MineTemplate
from ... import btm, router, state

TABS = ["active", "reserved", "sold", "saved"]
EMPTY = {"active": ("Nothing for sale right now", "Got something you don't use? Snap it, name it, and it's up in seconds."),
         "reserved": ("Nothing reserved", "Mark an item as reserved while a buyer is on the way."),
         "sold": ("Nothing sold yet", "Mark items as sold when they're gone: they stay on your page for a month as "
                                      "proof you're a good seller."),
         "saved": ("Nothing saved yet", "Tap the heart on anything you like to keep it here.")}


class Mine(MineTemplate):
    """#mine[/reserved|sold|saved] (members): what you sell by status (views, chats, quick actions in Items/MineRow:
    reserve, sold, back on sale, bump, edit, delete) and the items you saved. Each tab is its own address.
    Server: my_listings, my_saved (+ the row actions)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = args[0] if args and args[0] in TABS else "active"
        me = state.me() or {}
        state.set_attr(self.public_link, "href", router.href("seller", me.get("key")))
        self.rows.add_event_handler("x-changed", self._changed)
        self._load()

    def _changed(self, **event_args):
        self._load()

    def _load(self):
        d = state.call("my_listings")
        if d is None:
            return
        lists = d["lists"]
        self.spot_line.text = ("Selling from " + d["spot"]["label"]) if d.get("spot") else "No selling spot yet."
        counts = {"active": len(lists["active"]), "reserved": len(lists["reserved"]), "sold": len(lists["sold"]),
                  "saved": d.get("saved") or 0}
        for key, link, num in (("active", self.t_active, self.n_active), ("reserved", self.t_reserved, self.n_reserved),
                               ("sold", self.t_sold, self.n_sold), ("saved", self.t_saved, self.n_saved)):
            num.text = str(counts[key])
            link.classes["on"] = key == self.tab
            state.set_attr(link, "aria-current", "page" if key == self.tab else None)
        if self.tab == "saved":
            s = state.call("my_saved", btm.opts())
            items = list(s["items"]) if s else []
            self.saved.items, self.rows.items = items, []
        else:
            items = list(lists[self.tab])
            self.rows.items, self.saved.items = items, []
        self.saved.visible = self.tab == "saved" and bool(items)
        self.rows.visible = self.tab != "saved" and bool(items)
        self.empty.visible = not items
        self.empty_title.text, self.empty_text.text = EMPTY[self.tab]
        self.empty_sell.visible = self.tab == "active"
        self.empty_browse.visible = self.tab == "saved"
