from anvil import *

from ._anvil_designer import QuickChipTemplate


class QuickChip(QuickChipTemplate):
    """A one-tap message ("Is it still available?") on an item page or in a chat: item = {text}.
    A click raises x-quick(text) on the panel; the page puts the words in the message box."""

    def __init__(self, **properties):
        super().__init__(**properties)

    def pick_click(self, event):
        self.parent.raise_event("x-quick", text=self.item["text"])
