from anvil import *
from anvil.js import window

from ._anvil_designer import PhotoTemplate


class Photo(PhotoTemplate):
    """One photo in an item's swipeable strip: item = {src, alt, lazy}. A click shows it full screen (BTM.lightbox)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        img = self.dom_nodes["img"]
        img.src = self.item["src"]
        img.alt = self.item["alt"]
        if self.item.get("lazy"):
            img.setAttribute("loading", "lazy")

    def zoom_click(self, event):
        window.BTM.lightbox(self.item["src"], self.item["alt"])
