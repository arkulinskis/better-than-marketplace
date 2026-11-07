"""Dates of birth for the 18+ check (sign-up and the age gate). The server checks again (Accounts._check_age) and
keeps only the fact that the person confirmed it, never the date."""
import datetime

from . import state


def age_of(iso):
    """'1990-05-17' -> age in whole years today, or None when it isn't a date."""
    try:
        y, m, d = [int(x) for x in (iso or "").split("-")]
        born = datetime.date(y, m, d)
    except Exception:
        return None
    t = datetime.date.today()
    return t.year - born.year - (1 if (t.month, t.day) < (born.month, born.day) else 0)


def max_birthdate():
    t = datetime.date.today()
    return "%04d-%02d-%02d" % (t.year - 18, t.month, t.day)


def birth_input(box):
    """A TextBox becomes the browser's date picker (the App Server's TextBox has no type="date"); read it with
    state.control(box).value."""
    el = state.control(box)
    el.setAttribute("type", "date")
    el.setAttribute("max", max_birthdate())
    el.setAttribute("autocomplete", "bday")
