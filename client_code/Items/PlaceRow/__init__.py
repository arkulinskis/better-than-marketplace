from anvil import *

from ._anvil_designer import PlaceRowTemplate


class PlaceRow(PlaceRowTemplate):
    """Spot picker search result: item = {lat, lng, name, label}. A click raises x-pick(place) on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)

    def pick_click(self, event):
        self.parent.raise_event("x-pick", place=self.item)
