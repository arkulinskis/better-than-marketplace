from anvil import *
from anvil.js import window

from ._anvil_designer import AreaMapTemplate


class AreaMap(AreaMapTemplate):
    """An item's rough area: a ~1 km circle on an OpenStreetMap map (btm.js BTM.areaMap), never the exact spot.
    show_area(lat, lng, label) draws it; the map is removed when the page goes away."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self._map = None
        self._want = None

    def show_area(self, lat, lng, label=""):
        self.dom_nodes["msg"].textContent = ("Around " + label) if label else "Around here"
        self._want = (lat, lng)
        if self.visible and self.parent is not None:
            self._draw()

    def _draw(self):
        if self._want is None or self._map is not None:
            return
        self._map = window.BTM.areaMap(self.dom_nodes["map"], self._want[0], self._want[1])

    @handle("", "show")
    def form_show(self, **event_args):
        self._draw()

    @handle("", "hide")
    def form_hide(self, **event_args):
        if self._map is not None:
            self._map.destroy()
            self._map = None
