"""The app starts here (anvil.yaml: startup module). One server call to learn who is signed in (Anvil's loading
spinner shows meanwhile), the Privacy & Terms kit, then the page for the address in the browser bar."""
import anvil.server
from anvil.js import window

from . import legal, router, state
from . import session_guard

session_guard.start()  # an expired server session reloads quietly instead of "Session expired, refresh now"

LEGAL_THEME = {"accent": "#BF3A1A"}  # colours for the Privacy & Terms page (match --c-brand-text in app.css)

legal.setup(LEGAL_THEME)
window.APP_API = anvil.server.get_api_origin()  # listing photos are served at <api>/photo?k=... (btm.js BTM.photo)
state.set_me(anvil.server.call("get_me"))
if state.me():
    legal.refresh_soon()
router.start()
