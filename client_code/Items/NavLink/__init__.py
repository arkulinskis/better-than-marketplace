from anvil import *

from ._anvil_designer import NavLinkTemplate
from ... import router, state


class NavLink(NavLinkTemplate):
    """A main-menu link (header and phone tab bar). item = {page, label, icon, on, dot, bubble} from Shell.refresh:
    dot = unread messages on Chats; bubble = the big round Sell button in the middle of the phone tab bar."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_attr(self, "href", router.href(self.item["page"]))
        self.icon.classes.add("ic-" + self.item["icon"])
        self.classes["on"] = bool(self.item.get("on"))
        self.classes["tb-sell"] = bool(self.item.get("bubble"))
        n = self.item.get("dot") or 0
        self.dot.visible = self.dot_sr.visible = n > 0
        self.dot.text = "9+" if n > 9 else str(n)
