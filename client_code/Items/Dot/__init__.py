from anvil import *

from ._anvil_designer import DotTemplate


class Dot(DotTemplate):
    """One position dot over an item's photos (decoration; the photos have their own names). item = {on}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.set_on(bool(self.item.get("on")))

    def set_on(self, on):
        self.dot.classes["on"] = on
