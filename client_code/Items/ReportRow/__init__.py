from anvil import *

from ._anvil_designer import ReportRowTemplate
from ... import state
from ..AdminListing import AdminListing


class ReportRow(ReportRowTemplate):
    """Admin → Reports: one report (reason, who, when, details) and the listing it's about with the resolve buttons
    (Items/AdminListing in report mode). A resolved report raises x-changed on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.when.text = state.short_date(r.get("created")) + " · " + state.ago(r.get("created"))
        self.details.visible = bool(r.get("details"))
        listing = r.get("listing")
        self.gone.visible = listing is None
        if listing is not None:
            self.listing_slot.add_component(AdminListing(item=dict(
                listing, _report_id=r["id"], _report_open=r.get("status") == "open", _on_change=self._changed)))

    def _changed(self):
        self.parent.raise_event("x-changed")
