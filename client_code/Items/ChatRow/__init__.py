from anvil import *

from ._anvil_designer import ChatRowTemplate
from ... import btm, router, state


class ChatRow(ChatRowTemplate):
    """One chat in the Chats list: item = a Chat._summary dict (+ "on" when it's the open one)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        state.set_attr(self.row, "href", router.href("messages", c["key"]))
        self.row.classes["on"] = bool(c.get("on"))
        self.row.classes["unread"] = bool(c.get("unread"))
        if c.get("on"):
            state.set_attr(self.row, "aria-current", "true")
        img = self.dom_nodes["img"]
        if c.get("cover"):
            img.src = btm.photo(c["cover"], True)
        else:
            img.style.display = "none"
        self.ph.visible = not c.get("cover")
        self.who.text = ("Buying from " if c.get("role") == "buying" else "Selling to ") + (c.get("other") or "")
        self.last.text = ("You: " if c.get("last_mine") else "") + (c.get("last_text") or "")
        self.when.text = state.ago(c.get("last_at")).replace(" ago", "")
        n = c.get("unread") or 0
        self.dot.visible = n > 0
        self.dot.text = str(n)
        state.set_attr(self.dot, "aria-label", "%d unread" % n)
