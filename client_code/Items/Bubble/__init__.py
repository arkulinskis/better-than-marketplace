from anvil import *

from ._anvil_designer import BubbleTemplate


class Bubble(BubbleTemplate):
    """One line in a chat thread: item = {kind: "day" | "msg" | "note", text, time, mine}. Messages page builds the
    list (a day divider before each new day, a note when the item is sold or gone)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        kind = it.get("kind")
        self.host.classes["mine"] = bool(it.get("mine"))
        self.day.visible = kind == "day"
        self.bubble.visible = kind == "msg"
        self.note.visible = kind == "note"
        self.bubble.classes["mine"] = bool(it.get("mine"))
        if kind == "day":
            self.day.text = it["text"]
        elif kind == "note":
            self.note.text = it["text"]
        else:
            self.text.text = it["text"]
            self.time.text = it.get("time") or ""
