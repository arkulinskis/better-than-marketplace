"""Shared server helpers: time, permissions, input cleaning, rate limits, app settings.

Every other server module imports this as `from . import common as C`.
Rules every callable follows:
  - check who is calling (C.me() / C.require_user() / C.require_admin()) before touching data
  - return JSON-friendly values only (dicts, lists, str, numbers, bools, None); dates via C.iso()
  - expected problems return C.fail("Message the user can read"); the page shows it
"""
import datetime as dt
import re

import anvil.server
import anvil.users
from anvil.tables import app_tables


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(v):
    """date/datetime -> ISO string (datetimes in UTC), anything else unchanged."""
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=dt.timezone.utc)
        return v.astimezone(dt.timezone.utc).isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    return v


def fail(message):
    return {"ok": False, "error": message}


def ok(**data):
    data["ok"] = True
    return data


def text(value, limit=200, multiline=False):
    """Clean user text: str, trimmed, length-capped; single-line unless multiline."""
    s = "" if value is None else str(value)
    s = s.replace("\r\n", "\n").strip()
    if not multiline:
        s = re.sub(r"\s+", " ", s)
    else:
        s = re.sub(r"\n{3,}", "\n\n", s)
    return s[:limit]


def me():
    return anvil.users.get_user()


def require_user():
    u = anvil.users.get_user()
    if u is None:
        raise anvil.server.PermissionDenied("Please sign in first.")
    return u


def is_admin(user):
    return bool(user is not None and user["is_admin"])


def require_admin():
    u = require_user()
    if not is_admin(u):
        raise anvil.server.PermissionDenied("Only admins can do that.")
    return u


def name_of(user):
    if user is None:
        return "Someone"
    return user["display_name"] or (user["email"] or "Someone").split("@")[0].capitalize()


def row_by_id(table, row_id):
    """get_by_id that returns None for a missing or malformed id (ids come from the browser)."""
    if not isinstance(row_id, str) or not row_id:
        return None
    try:
        return table.get_by_id(row_id)
    except Exception:
        return None


def rate_limited(key, limit, seconds):
    """True if this browser session already did `key` `limit` times in the last `seconds`."""
    stamp = now()
    store = "rate_" + key
    recent = [t for t in (anvil.server.session.get(store) or [])
              if (stamp - dt.datetime.fromisoformat(t)).total_seconds() < seconds]
    if len(recent) >= limit:
        return True
    anvil.server.session[store] = recent + [stamp.isoformat()]
    return False


def get_setting(key, default=None):
    row = app_tables.app_settings.get(key=key)
    return default if row is None else row["value"]


def set_setting(key, value):
    row = app_tables.app_settings.get(key=key)
    if row is None:
        app_tables.app_settings.add_row(key=key, value=value)
    else:
        row["value"] = value


# ----------------------------------------------------------------------------------------------- this app
import math  # noqa: E402
import secrets  # noqa: E402

MIN_AGE = 18
_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no look-alikes (l, 1, o, 0)


def token(n=10):
    """A random, URL-safe key (listings, photos, chats, public profile links)."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def km_between(lat1, lng1, lat2, lng2):
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def coord(v, limit):
    """A latitude (limit 90) or longitude (limit 180) from the browser, or None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or abs(v) > limit:
        return None
    return float(v)


def public_key(user):
    """The user's public profile key (#seller/<key>), made on first use."""
    if not user["public_key"]:
        user["public_key"] = token(8)
    return user["public_key"]


def is_adult(user):
    return bool(user is not None and user["adult_confirmed_at"])


def has_spot(user):
    return bool(user is not None and user["spot_lat"] is not None and user["spot_lng"] is not None and user["spot_label"])


def require_adult():
    """Signed in and confirmed 18+ (sign-up asks for the date of birth)."""
    u = require_user()
    if not is_adult(u):
        raise anvil.server.PermissionDenied("Please confirm you're %d or older first." % MIN_AGE)
    return u


def age_on(birthdate, today=None):
    today = today or now().date()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def parse_birthdate(value):
    """'YYYY-MM-DD' -> date, or None when missing, malformed, in the future or absurd."""
    try:
        d = dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None
    age = age_on(d)
    return d if 0 <= age <= 120 else None
