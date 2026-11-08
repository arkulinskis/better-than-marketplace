from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import AgeGateTemplate
from ... import state
from ...ages import age_of, birth_input, max_birthdate


class AgeGate(AgeGateTemplate):
    """The 18+ check for an account that hasn't confirmed its age yet (Sell, asking a seller, sending a message).
    Closes with the updated me, or None. Under 18: the server switches the account off and signs it out, and the
    page goes back to the landing page."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.heading(self.title, 2)
        birth_input(self.dob_box)

    def _err(self, message):
        self.error.text = message or ""
        self.error.visible = bool(message)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        value = state.control(self.dob_box).value or ""
        age = age_of(value)
        if age is None:
            self._err("Please enter your date of birth.")
            return
        self.ok_button.enabled = False
        try:
            r = anvil.server.call("confirm_age", value)
        finally:
            self.ok_button.enabled = True
        if not r.get("ok"):
            self._err(r.get("error"))
            if age < 18:
                window.setTimeout(_restart, 2500)
            return
        state.set_me(r["me"])
        self.raise_event("x-close-alert", value=r["me"])


def _restart(*args):
    """An under-18 account was switched off and signed out: start again from the landing page."""
    window.location.hash = "#landing"
    window.location.reload()
