from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import SellerTemplate
from ... import btm, state


class Seller(SellerTemplate):
    """#seller/<publicKey> (for everyone): a seller's public page. Who they are (name, area, member since, how many
    sold), what they sell now, and what they sold in the last 30 days. Server: seller_page."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        r = anvil.server.call("seller_page", args[0] if args else "", btm.opts())
        ok = bool(r.get("ok"))
        self.missing.visible, self.found.visible = not ok, ok
        if not ok:
            self.missing_title.text = r.get("error") or "That seller doesn't exist."
            state.heading(self.missing_title, 1)
            return
        s, mine = r["seller"], bool(r.get("mine"))
        window.document.title = s["name"] + " · Better Than Marketplace"
        self.initials.text = state.initials(s["name"])
        self.name.text = s["name"]
        state.heading(self.name, 1)
        self.area_box.visible = bool(s.get("area"))
        self.area.text = s.get("area") or ""
        self.since.text = "Member since " + btm.long_date(s.get("since"))
        self.sold_count.text = "%d sold" % s["sold"]
        self.active_count.text = "%d for sale" % s["active"]
        self.demo_box.visible = bool(s.get("demo"))
        self.mine_box.visible = mine
        self.selling_title.text = "You're selling" if mine else btm.first_name(s["name"]) + " is selling"
        state.heading(self.selling_title, 2)
        self.items.items = r["items"]
        self.items_empty.visible = not r["items"]
        self.items_empty_text.text = "Snap something you don't need any more." if mine else "Check back soon."
        self.sold_box.visible = bool(r["sold"])
        self.sold.items = r["sold"]
