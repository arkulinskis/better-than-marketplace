import json

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import SpotPickerTemplate
from ... import state


class SpotPicker(SpotPickerTemplate):
    """The spot picker: a map with a pin (btm.js BTM.pickerMap), "Use my location", a place search (Nominatim, on a tap
    only) and the area name. Opened by btm.pick_spot(); closes with {lat, lng, label}, {"extra": key} for an extra
    button (Browse: "My selling spot", "Anywhere"), or None."""

    def __init__(self, title="Where are you?", text="", hint="Tap the map to move the pin.", label=None, lat=None,
                 lng=None, ok="Save", require_label=True, label_title="Name of the area", extra=(), **properties):
        super().__init__(**properties)
        self.title.text = title
        state.heading(self.title, 2)
        self.text.text, self.text.visible = text, bool(text)
        self.hint.text = hint
        self.label_box.text = label or ""
        self.ok_button.text = ok
        self._require = require_label
        self._auto = not label  # fill the area name from the map until the person types one
        self._pos = {"lat": lat, "lng": lng} if lat is not None and lng is not None else None
        self._extra = list(extra or [])
        for btn, ex in zip([self.extra1, self.extra2], self._extra + [None, None]):
            btn.visible = ex is not None
            if ex is not None:
                btn.text = ex[1]
                btn.tag = ex[0]
        self.results_box.visible = False
        self._map = None
        self.results.add_event_handler("x-pick", self._picked)
        state.set_control_attr(self.search_box, "type", "search")
        state.set_control_attr(self.search_box, "aria-label", "Search a place")
        anvil.js.get_dom_node(self.label_title).textContent = label_title

    @handle("", "show")
    def form_show(self, **event_args):
        if self._map is None:
            p = self._pos or {}
            self._map = window.BTM.pickerMap(self.dom_nodes["map"], p.get("lat"), p.get("lng"), self._moved)

    @handle("", "hide")
    def form_hide(self, **event_args):
        if self._map is not None:
            self._map.destroy()
            self._map = None

    # ---- the pin
    def _moved(self, lat, lng):
        """A tap on the map or a dragged pin: remember it and, if the name is still ours, look the area up."""
        self._set(lat, lng, look_up=True)

    def _set(self, lat, lng, zoom=None, look_up=False, move_map=False):
        self._pos = {"lat": float(lat), "lng": float(lng)}
        self._err("")
        if move_map and self._map is not None:
            self._map.setPos(lat, lng, zoom)
        if look_up and self._auto:
            name = window.BTM.reverse(lat, lng)
            if name and self._auto:
                self.label_box.text = name

    @handle("label_box", "change")
    def label_box_change(self, **event_args):
        self._auto = not (self.label_box.text or "").strip()

    @handle("locate_button", "click")
    def locate_button_click(self, **event_args):
        self.locate_button.enabled = False
        try:
            p = window.BTM.locate()
            self._set(p.lat, p.lng, 14, look_up=True, move_map=True)
        except Exception as e:
            self._err(_message(e, "We couldn't get your location. Allow it in your browser, or search a place."))
        finally:
            self.locate_button.enabled = True

    # ---- place search
    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        self.search_button_click()

    @handle("search_button", "click")
    def search_button_click(self, **event_args):
        text = (self.search_box.text or "").strip()
        if len(text) < 2:
            return
        self.search_button.enabled = False
        try:
            found = json.loads(window.BTM.search(text))
            self.results.items = found
            self.results_note.text = "" if found else "No place found. Try another spelling, or tap the map."
        except Exception:
            self.results.items = []
            self.results_note.text = "Search isn't working right now. Tap the map instead."
        finally:
            self.search_button.enabled = True
        self.results_note.visible = bool(self.results_note.text)
        self.results_box.visible = True

    def _picked(self, place, **event_args):
        if self._auto or not (self.label_box.text or "").strip():
            self.label_box.text = place["name"]
            self._auto = True
        self._set(place["lat"], place["lng"], 14, move_map=True)
        self.results_box.visible = False

    # ---- closing
    def _err(self, message):
        self.error.text = message or ""
        self.error.visible = bool(message)

    def _extra_click(self, btn):
        self.raise_event("x-close-alert", value={"extra": btn.tag})

    @handle("extra1", "click")
    def extra1_click(self, **event_args):
        self._extra_click(self.extra1)

    @handle("extra2", "click")
    def extra2_click(self, **event_args):
        self._extra_click(self.extra2)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        label = (self.label_box.text or "").strip()
        if not self._pos:
            self._err("Put a pin on the map first (tap the map, use your location, or search).")
            return
        if self._require and len(label) < 2:
            self._err("Give the area a name, like a neighbourhood or a town.")
            self.label_box.focus()
            return
        self.raise_event("x-close-alert", value={"lat": self._pos["lat"], "lng": self._pos["lng"],
                                                 "label": label or "Pinned spot"})


def _message(e, fallback):
    text = str(e) or ""
    return text.split(": ", 1)[-1] if text else fallback
