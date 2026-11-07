from anvil import *

from ._anvil_designer import ProfileTemplate
from ... import auth, btm, router, state


class Profile(ProfileTemplate):
    """#profile: your name, where you sell from (the map picker), the 18+ check, light/dark, a password reset link,
    Privacy & Terms, feedback, sign out."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        state.heading(self.name_title, 1)
        state.set_control_attr(self.name_box, "autocomplete", "name")
        state.set_control_attr(self.name_box, "maxlength", "60")
        self._show_me()
        self._show_theme()

    def _show_me(self):
        me = state.me()
        self.initials.text = state.initials(me.get("name"))
        self.name_title.text = me.get("name") or ""
        joined = state.month_year(me.get("joined"))
        self.email_line.text = (me.get("email") or "") + (" · member since " + joined if joined else "")
        self.name_box.text = me.get("name") or ""
        self.admin_link.visible = bool(me.get("is_admin"))
        spot = me.get("spot")
        self.spot_text.text = ("Buyers see %s and how far away it is, never your address." % spot["label"]) if spot \
            else "Not set yet. You need it to sell."
        self.spot_button.text = "Change" if spot else "Set my spot"
        self.spot_button.role = ["btn"] if spot else ["btn", "btn-primary"]
        self.adult_badge.visible = bool(me.get("adult"))
        self.age_button.visible = not me.get("adult")
        state.set_attr(self.public_link, "href", router.href("seller", me.get("key")))

    def _changed(self):
        """The name, spot or age changed: redraw this page and the header's account menu."""
        self._show_me()
        shell = getattr(self, "layout", None)
        if shell is not None and hasattr(shell, "refresh"):
            shell.refresh("profile")

    def _show_theme(self):
        t = state.theme()
        for name, el in (("auto", self.theme_auto), ("light", self.theme_light), ("dark", self.theme_dark)):
            el.classes["on"] = name == t

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-pick"))
        self._show_theme()

    @handle("spot_button", "click")
    def spot_button_click(self, **event_args):
        if btm.edit_spot():
            self._changed()

    @handle("age_button", "click")
    def age_button_click(self, **event_args):
        if btm.age_gate():
            self._changed()

    @handle("name_box", "pressed_enter")
    def name_box_pressed_enter(self, **event_args):
        self.save_button_click()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        name = (self.name_box.text or "").strip()
        if len(name) < 2:
            state.toast("Please tell us your name.", "error")
            return
        r = state.call("update_profile", name)
        if r:
            state.set_me(r["me"])
            self._changed()
            state.toast("Saved", "ok")

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        r = auth.reset(state.me()["email"])
        state.toast(r["message"], "ok")

    def feedback_click(self, event):
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.set_unread(0)
        state.toast("Signed out. See you soon!")
        router.go("landing")
