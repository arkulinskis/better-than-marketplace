"""Who is signed in, their profile, the 18+ check and their selling spot.

ADMIN_EMAILS become admins the first time they sign in. Email confirmation is off (USERS_CONFIG in
tools/sync_to_anvil.py), so whoever first registers one of these emails gets admin: sign up with it
yourself right after the app goes live.

Accounts are 18+: sign-up asks for the date of birth (finish_signup). We keep only the moment the person
confirmed it (users.adult_confirmed_at), never the date itself. Someone under 18 gets their new account
switched off straight away.
"""
import anvil.server
import anvil.users
from anvil.tables import app_tables

from . import common as C

ADMIN_EMAILS = {"arkulinskis@gmail.com"}


def spot_dict(user):
    if not C.has_spot(user):
        return None
    return {"label": user["spot_label"], "lat": user["spot_lat"], "lng": user["spot_lng"]}


def me_dict(user):
    if user is None:
        return None
    return {"id": user.get_id(), "email": user["email"], "name": C.name_of(user),
            "is_admin": C.is_admin(user), "joined": C.iso(user["signed_up"]),
            "key": C.public_key(user), "adult": C.is_adult(user), "spot": spot_dict(user)}


@anvil.server.callable
def get_me():
    """The signed-in user (or None). Called when the app starts and after signing in."""
    user = anvil.users.get_user()
    if user is None:
        return None
    changes = {}
    if (user["email"] or "").lower() in ADMIN_EMAILS and not user["is_admin"]:
        changes["is_admin"] = True
    seen = user["last_seen"]
    if seen is None or (C.now() - seen).total_seconds() > 3600:
        changes["last_seen"] = C.now()
    if changes:
        user.update(**changes)
    return me_dict(user)


@anvil.server.callable(require_user=True)
def update_profile(name):
    user = C.require_user()
    name = C.text(name, 60)
    if len(name) < 2:
        return C.fail("Please use at least 2 characters for your name.")
    user["display_name"] = name
    return C.ok(me=me_dict(user))


def _check_age(user, birthdate):
    d = C.parse_birthdate(birthdate)
    if d is None:
        return C.fail("Please enter your date of birth.")
    if C.age_on(d) < C.MIN_AGE:
        user["enabled"] = False
        anvil.users.logout()
        return C.fail("Sorry, you need to be %d or older to use Better Than Marketplace." % C.MIN_AGE)
    if not user["adult_confirmed_at"]:
        user["adult_confirmed_at"] = C.now()
    return None


@anvil.server.callable(require_user=True)
def finish_signup(name, birthdate):
    """Right after signup_with_email (client_code/Main.py): the name and the 18+ check."""
    user = C.require_user()
    problem = _check_age(user, birthdate)
    if problem:
        return problem
    name = C.text(name, 60)
    if len(name) >= 2:
        user["display_name"] = name
    return C.ok(me=me_dict(user))


@anvil.server.callable(require_user=True)
def confirm_age(birthdate):
    """For an account that hasn't confirmed its age yet (the age gate on Sell and in chats)."""
    user = C.require_user()
    return _check_age(user, birthdate) or C.ok(me=me_dict(user))


@anvil.server.callable(require_user=True)
def set_spot(label, lat, lng):
    """Where you sell from: an area name everyone sees and a point we keep to ~100 m (only distances are shown)."""
    user = C.require_user()
    label, lat, lng = C.text(label, 60), C.coord(lat, 90), C.coord(lng, 180)
    if len(label) < 2:
        return C.fail("Give your area a name, like a neighbourhood or a town.")
    if lat is None or lng is None:
        return C.fail("Pick a spot on the map first.")
    user.update(spot_label=label, spot_lat=round(lat, 3), spot_lng=round(lng, 3))
    # what's still for sale moves with you
    for r in app_tables.listings.search(owner=user):
        if r["status"] in ("active", "reserved"):
            r.update(area=user["spot_label"], lat=user["spot_lat"], lng=user["spot_lng"])
    return C.ok(me=me_dict(user))
