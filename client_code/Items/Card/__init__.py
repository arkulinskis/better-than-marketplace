from anvil import *

from ._anvil_designer import CardTemplate
from ... import btm, router, state


class Card(CardTemplate):
    """One listing as a card (Browse, Landing, Seller, Item "More from", Mine → Saved, the "It's for sale!" preview).
    item = a card dict from Market.card(): key, title, price, price_mode, status, area, dist, cover, photos, posted,
    sold_at, demo, mine, saved, hidden. Item extra "_no_heart" hides the heart (the Sell preview)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        state.heading(self.title, 3)
        sold = it.get("status") == "sold"
        self.card.classes["is-sold"] = sold
        state.set_attr(self.link, "href", router.href("item", it["key"]))
        state.set_attr(self.link, "aria-label", "%s, %s" % (it["title"], btm.price(it)))
        img = self.dom_nodes["img"]
        if it.get("cover"):
            img.src = btm.photo(it["cover"], True)
        else:
            img.style.display = "none"
        self.stamp.visible = sold
        self.tag.visible = not sold
        if not sold:
            btm.tag(self.tag, it)
        if it.get("status") == "reserved":
            self.ribbon.text, self.ribbon.role, self.ribbon.visible = "Reserved", ["ribbon", "badge", "badge-ink"], True
        elif it.get("hidden"):
            self.ribbon.text, self.ribbon.role, self.ribbon.visible = "Hidden", ["ribbon", "badge", "badge-bad"], True
        self.count_box.visible = (it.get("photos") or 0) > 1 and not sold
        self.count.text = str(it.get("photos") or 0)
        state.set_attr(self.count_box, "aria-label", "%d photos" % (it.get("photos") or 0))
        self.heart.visible = not (it.get("_no_heart") or it.get("mine") or sold)
        self.heart.classes["on"] = bool(it.get("saved"))
        state.set_attr(self.heart, "aria-pressed", "true" if it.get("saved") else "false")
        state.set_attr(self.heart, "data-save", it["key"])
        state.set_attr(self.heart, "aria-label", "Save " + it["title"])
        place = btm.dist(it["dist"]) if it.get("dist") is not None else it.get("area") or ""
        self.where_box.visible = bool(place)
        self.where.text = place
        self.when.text = ("sold " + state.ago(it["sold_at"])) if sold and it.get("sold_at") else state.ago(it.get("posted"))
        self.yours.visible = bool(it.get("mine"))
        self.demo.visible = bool(it.get("demo"))

    def heart_click(self, event):
        event.preventDefault()
        saved = btm.toggle_save(self.item["key"])
        if saved is not None:
            self.item["saved"] = saved
