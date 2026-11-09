import datetime

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ShellTemplate
from ... import auth, router, state

THEMES = ["auto", "light", "dark"]
_poll: dict = {"timer": None, "shell": None}


class Shell(ShellTemplate):
    """The frame around every page: header (menu for members; Browse / Sign in / Join for visitors), the account menu,
    the footer and the phone tab bar (Sell is the big round button in the middle). Pages use it with
    <anvil-form layout="Better_Than_Marketplace.Layouts.Shell">.

    Anvil keeps ONE Shell while pages come and go (open_form only swaps the "content" slot when the layout matches),
    so everything that depends on who is signed in or which page is open is drawn in refresh(), which router.show()
    calls after every page change. Unread chat messages: a quiet check every 40 s while the tab is visible, and
    shortly after every page change (the dot on Chats)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.copyright_label.text = "© %d Better Than Marketplace" % datetime.date.today().year
        self._outside = anvil.js.report_exceptions(self._close_menu_outside)
        self._keys = anvil.js.report_exceptions(self._key)
        self._page = ""
        self.refresh("")

    def refresh(self, page):
        self._page = page
        me = state.me()
        self.classes.update({"signed-in": bool(me), "signed-out": not me})
        self.member_actions.visible = bool(me)
        self.nav.visible = bool(me)
        self.guest_actions.visible = not me and page != "auth"
        self.guest_browse.visible = page != "browse"
        self.tabbar.visible = bool(me)
        self.menu.visible = False
        state.set_attr(self.brand, "href", "#browse" if me else "#landing")
        self._draw_nav()
        self.tab_profile.classes["on"] = page == "profile"
        if me:
            self.avatar_button.text = state.initials(me.get("name"))
            self.menu_name.text = me.get("name") or ""
            self.menu_email.text = me.get("email") or ""
            spot = me.get("spot")
            self.menu_spot.visible = bool(spot)
            self.menu_spot.text = ("Selling from " + spot["label"]) if spot else ""
            state.set_attr(self.public_link, "href", router.href("seller", me.get("key")))
            self.admin_link.visible = bool(me.get("is_admin"))
            _poll["shell"] = self
            window.setTimeout(_check_badges, 900)
        self._show_theme()

    def _draw_nav(self):
        me, page, n = state.me(), self._page, state.unread()
        if not me:
            self.nav_panel.items = []
            self.tab_panel.items = []
            return
        links = [{"page": p, "label": label, "icon": icon, "on": p == page, "dot": n if p == "messages" else 0}
                 for p, label, icon in router.NAV]
        self.nav_panel.items = links
        self.tab_panel.items = [dict(link, bubble=link["page"] == "sell") for link in links]

    def set_unread(self, n):
        n = n or 0
        if n == state.unread():
            return
        state.set_unread(n)
        self._draw_nav()

    # ---- account menu
    @handle("avatar_button", "click")
    def avatar_button_click(self, **event_args):
        self.menu.visible = not self.menu.visible
        state.set_control_attr(self.avatar_button, "aria-expanded", "true" if self.menu.visible else "false")

    def _close_menu_outside(self, event):
        if self.menu.visible and not event.target.closest(".anvil-role-avatar, .ui-menu .ui-seg"):
            self.menu.visible = False

    def _key(self, event):
        if getattr(event, "key", None) == "Escape":
            self.menu.visible = False

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("click", self._outside, True)
        window.document.addEventListener("keydown", self._keys)
        if _poll["timer"] is None:
            _poll["timer"] = window.setInterval(_check_badges, 40000)
            window.document.addEventListener("visibilitychange", _check_badges)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("click", self._outside, True)
        window.document.removeEventListener("keydown", self._keys)

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-set"))
        self._show_theme()

    def _show_theme(self):
        t = state.theme()
        for name, el in zip(THEMES, [self.theme_auto, self.theme_light, self.theme_dark]):
            el.classes["on"] = name == t

    def feedback_click(self, event):
        self.menu.visible = False
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.set_unread(0)
        state.toast("Signed out. See you soon!")
        router.go("landing")


def _check_badges(*args):
    """Unread messages for the dot on Chats (no spinner, nothing shown if it fails)."""
    shell = _poll["shell"]
    if shell is None or not state.me() or window.document.hidden:
        return
    try:
        b = state.call_quiet("badges")
    except Exception:
        return  # signed out in another tab, session ended: the next page change asks again
    if isinstance(b, dict):
        shell.set_unread(b.get("unread") or 0)
