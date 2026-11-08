from anvil import *

from ._anvil_designer import EmptyArtTemplate


class EmptyArt(EmptyArtTemplate):
    """The empty-state drawing: an empty price tag on a string. Decoration only (aria-hidden)."""

    def __init__(self, **properties):
        super().__init__(**properties)
