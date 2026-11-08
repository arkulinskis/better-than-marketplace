from anvil import *

from ._anvil_designer import TileTemplate
from ... import state


class Tile(TileTemplate):
    """A photo in the Sell tray: item = {id, src, state ("up" | "ok" | "err"), index}. Raises on the panel:
    x-cover(id) (tap a photo to make it the cover), x-remove(id), x-retry(id)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        if it.get("src"):
            self.dom_nodes["img"].src = it["src"]
        self.dom_nodes["img"].alt = "Photo %d" % (it["index"] + 1)
        first = it["index"] == 0
        self.cover.visible = first
        state.set_attr(self.pick, "aria-label", "Photo %d (cover)" % (it["index"] + 1) if first
                       else "Photo %d: make it the cover photo" % (it["index"] + 1))
        self.busy.visible = it.get("state") == "up"
        self.failed.visible = it.get("state") == "err"

    def pick_click(self, event):
        self.parent.raise_event("x-cover", tile_id=self.item["id"])

    def remove_click(self, event):
        self.parent.raise_event("x-remove", tile_id=self.item["id"])

    def retry_click(self, event):
        self.parent.raise_event("x-retry", tile_id=self.item["id"])
