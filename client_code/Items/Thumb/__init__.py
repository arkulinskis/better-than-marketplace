from anvil import *

from ._anvil_designer import ThumbTemplate
from ... import state


class Thumb(ThumbTemplate):
    """A photo thumbnail under an item's gallery (desktop): item = {src, index, on}. A click raises x-thumb(index)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.dom_nodes["img"].src = self.item["src"]
        self.btn.classes["on"] = bool(self.item.get("on"))
        state.set_attr(self.btn, "aria-label", "Photo %d" % (self.item["index"] + 1))

    def set_on(self, on):
        self.btn.classes["on"] = on
        state.set_attr(self.btn, "aria-current", "true" if on else None)

    def pick_click(self, event):
        self.parent.raise_event("x-thumb", index=self.item["index"])
