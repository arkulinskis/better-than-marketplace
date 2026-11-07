from anvil import *
import anvil.server

from ._anvil_designer import LandingTemplate
from ... import btm, state

# The app's video on the Addanapp YouTube channel (APP_MAKER/youtube/manifest.json), shown in the Watch section.
YT_VIDEO = "X374nwXR8Qs"


class Landing(LandingTemplate):
    """#landing (Persuade; also "How it works" for members): the live-map hero (things for sale pinned around the blue
    dot), the Watch section (the YouTube video), how it works, a live strip of what's for sale (server: browse),
    why it's better, features, questions. Static copy lives in the template."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        me = state.me()
        self.guest_cta.visible = self.band_guest.visible = not me
        self.member_cta.visible = self.band_member.visible = bool(me)
        self.dom_nodes["yt_cover"].addEventListener("click", self._play)
        self._load_live()

    def _load_live(self):
        try:
            d = anvil.server.call("browse", btm.opts(sort="near" if btm.where() else "new", limit=8))
        except Exception:
            self.live_panel.items, self.live_empty.visible = [], False
            return
        if d.get("origin"):
            self.live_where.text = "For sale near %s, closest first." % d["origin"]["label"]
        self.live_panel.items = d["items"]
        self.live_empty.visible = not d["items"]

    def _play(self, event):
        """Swap the video's cover for YouTube's player (privacy-enhanced); nothing loads from YouTube before this click."""
        self.dom_nodes["yt_frame"].innerHTML = (
            '<iframe src="https://www.youtube-nocookie.com/embed/' + YT_VIDEO + '?autoplay=1&rel=0&playsinline=1" '
            'title="Better Than Marketplace video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" '
            'allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>')
