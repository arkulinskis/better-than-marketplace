from anvil import *

from ._anvil_designer import ReportTemplate
from ... import state


class Report(ReportTemplate):
    """Report a listing to the moderators (server: report_listing). Closes with True when sent."""

    def __init__(self, key, **properties):
        super().__init__(**properties)
        self._key = key
        state.heading(self.title, 2)
        state.set_control_attr(self.details_box, "maxlength", "600")

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=False)

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        reason = "other"
        for rb in (self.r_prohibited, self.r_scam, self.r_offensive, self.r_wrong, self.r_other):
            if rb.selected:
                reason = rb.value
        self.send_button.enabled = False
        try:
            r = state.call("report_listing", self._key, reason, self.details_box.text or "")
        finally:
            self.send_button.enabled = True
        if r is not None:
            self.raise_event("x-close-alert", value=True)
