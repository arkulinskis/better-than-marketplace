import json

from anvil import *
from anvil.js import window

from ._anvil_designer import PickupPlanTemplate
from ... import state

DAYS = 14


def _two(n):
    return ("0%d" % n) if n < 10 else str(n)


class PickupPlan(PickupPlanTemplate):
    """Plan a pickup from a chat: a day, a time and a public place, with "Find a safe spot nearby" (btm.js
    BTM.safeSpots: police stations, libraries, metro stations and malls around the item's rough area, from
    OpenStreetMap, on a tap only). Closes with {at, label, place, lat, lng} (at = ISO time from this browser's clock,
    label = how this browser writes it) or False. Opened by Pages/Messages; the server call is the page's."""

    def __init__(self, other="", spot=None, place="", **properties):
        super().__init__(**properties)
        state.heading(self.title, 2)
        self.text.text = ("Suggest a time and a public place. %s gets a card in the chat to confirm."
                          % (other or "The other person"))
        self._spot = spot if isinstance(spot, dict) and spot.get("lat") is not None else None
        self._pos = None
        self.find_button.visible = self._spot is not None
        self.results_box.visible = False
        self.results.add_event_handler("x-pick", self._picked)
        self.place_box.text = place or ""
        state.set_control_attr(self.place_box, "maxlength", "120")
        self._fill_days()
        self._fill_times()

    # ---- day and time (this browser's clock and language)
    def _date(self, offset):
        d = window.Date()
        d.setHours(0, 0, 0, 0)
        d.setDate(d.getDate() + offset)
        return d

    def _fill_days(self):
        items = []
        for i in range(DAYS):
            d = self._date(i)
            name = d.toLocaleDateString([], {"weekday": "short", "day": "numeric", "month": "short"})
            items.append(("Today" if i == 0 else "Tomorrow" if i == 1 else name, i))
        self.day_box.items = items
        now = window.Date()
        # late in the evening, tomorrow is the sensible default
        self.day_box.selected_value = 1 if now.getHours() >= 20 else 0
        state.set_control_attr(self.day_box, "aria-label", "Day")

    def _fill_times(self):
        items = []
        for h in range(7, 23):
            for m in (0, 30):
                d = window.Date(2000, 0, 1, h, m)
                items.append((d.toLocaleTimeString([], {"hour": "numeric", "minute": "2-digit"}), "%s:%s" % (_two(h), _two(m))))
        self.time_box.items = items
        self._default_time()
        state.set_control_attr(self.time_box, "aria-label", "Time")

    def _default_time(self):
        if self.day_box.selected_value == 0:
            now = window.Date()
            mins = now.getHours() * 60 + now.getMinutes() + 90   # at least an hour from now, on the half hour
            h, m = min(22, mins // 60), 30 if mins % 60 >= 30 else 0
            if h < 7:
                h, m = 7, 0
            self.time_box.selected_value = "%s:%s" % (_two(h), _two(m))
        else:
            self.time_box.selected_value = "18:00"

    @handle("day_box", "change")
    def day_box_change(self, **event_args):
        self._default_time()
        self._err("")

    def _when(self):
        """(Date, ISO, label) for the chosen day and time, or None when it's already past."""
        d = self._date(int(self.day_box.selected_value or 0))
        h, m = [int(x) for x in str(self.time_box.selected_value or "18:00").split(":")]
        d.setHours(h, m, 0, 0)
        if d.getTime() < window.Date.now() - 5 * 60000:
            return None
        label = "%s, %s" % (d.toLocaleDateString([], {"weekday": "short", "day": "numeric", "month": "short"}),
                            d.toLocaleTimeString([], {"hour": "numeric", "minute": "2-digit"}))
        return d.toISOString(), label

    # ---- safe spots
    @handle("find_button", "click")
    def find_button_click(self, **event_args):
        if self._spot is None:
            return
        self.find_button.enabled = False
        self.find_button.text = "Looking around…"
        self.results.items = []
        self.results_note.text = ""
        try:
            found = json.loads(window.BTM.safeSpots(self._spot["lat"], self._spot["lng"]))
            self.results.items = found
            self.results_note.text = ("Tap one to use it." if found else
                                      "No police station, library or metro close by on the map. Type a busy public place instead.")
        except Exception:
            self.results_note.text = "The map service didn't answer. Type a busy public place instead (a metro entrance, a café)."
        finally:
            self.find_button.enabled = True
            self.find_button.text = "Find a safe spot nearby"
        self.results_box.visible = True

    def _picked(self, place, **event_args):
        kind, name = place.get("kind") or "", place.get("name") or ""
        self.place_box.text = name if not kind or name == kind or kind.lower() in name.lower() else "%s (%s)" % (name, kind.lower())
        self._pos = {"lat": place.get("lat"), "lng": place.get("lng")}
        self.results_box.visible = False
        self._err("")

    # ---- buttons
    def _err(self, message):
        self.error.text = message or ""
        self.error.visible = bool(message)

    @handle("place_box", "change")
    def place_box_change(self, **event_args):
        self._pos = None  # typed by hand: no map point

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=False)

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        when = self._when()
        if when is None:
            self._err("That time has already passed. Pick a later one.")
            return
        place = (self.place_box.text or "").strip()
        if not place:
            self._err("Say where to meet: a public place is best.")
            state.focus(self.place_box)
            return
        pos = self._pos or {}
        self.raise_event("x-close-alert", value={"at": when[0], "label": when[1], "place": place,
                                                 "lat": pos.get("lat"), "lng": pos.get("lng")})
