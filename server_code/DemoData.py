"""Demo content, so the app never looks empty. Loaded automatically the first time anyone opens the app
(ensure_loaded), removed or reloaded from Admin -> Demo data. Removing it is remembered: it doesn't come back.

Demo sellers have is_demo=True and @example.com emails; they can't sign in (no password). Every demo row
is flagged is_demo=True, so remove() deletes exactly what load() added (plus real people's chats with demo
sellers, and their saves / reports of demo items, which would otherwise point at nothing).
The listings' pictures are drawn (DemoArt.py), around Montréal neighbourhoods.
"""
import datetime as dt

import anvil
from anvil.tables import app_tables

from . import common as C
from . import DemoArt

# name, email, area, lat, lng
DEMO_USERS = [
    ("Maya Chen", "maya.demo@example.com", "Mile End", 45.5246, -73.5996),
    ("Théo Martin", "theo.demo@example.com", "Plateau-Mont-Royal", 45.5223, -73.5795),
    ("Inès Ozola", "ines.demo@example.com", "Verdun", 45.4592, -73.5689),
    ("Sam Okafor", "sam.demo@example.com", "Rosemont", 45.5436, -73.5778),
    ("Léa Tremblay", "lea.demo@example.com", "Villeray", 45.5441, -73.6232),
    ("Jonah Weiss", "jonah.demo@example.com", "Outremont", 45.5168, -73.6071),
    ("Priya Nair", "priya.demo@example.com", "Notre-Dame-de-Grâce", 45.4727, -73.6198),
    ("Lucas Moreau", "lucas.demo@example.com", "Saint-Henri", 45.4788, -73.5852),
]
# seller, title, art, price_mode, price, note, hours ago, status, photos
DEMO_LISTINGS = [
    (0, "Yellow velvet armchair", "armchair", "price", 85, "Super comfy, a tiny mark on the left arm. You carry it down (2nd floor, no elevator).", 2, "active", 3),
    (1, "Road bike, 54 cm", "bike", "price", 220, "Shifts smoothly, new tubes in September. Helmet included if you want it.", 5, "active", 3),
    (2, "Monstera in terracotta pot", "plant", "price", 30, "Big and happy, just too big for my window.", 1, "active", 2),
    (3, "Acoustic guitar", "guitar", "offer", None, "Plays fine, needs new strings. Make me an offer!", 9, "active", 2),
    (4, "Film camera (35 mm)", "camera", "price", 140, "Tested with a roll last month, photos came out great.", 26, "active", 3),
    (5, "Box of paperbacks", "books", "free", None, "About 30 novels, mostly mysteries. Take the whole box.", 3, "active", 2),
    (6, "White sneakers, size 9", "sneakers", "price", 25, "Worn twice. Wrong size for me.", 30, "active", 2),
    (7, "Teal teapot", "teapot", "price", 12, "", 4, "active", 1),
    (0, "Record player", "turntable", "price", 95, "Belt drive, built-in preamp. Two records thrown in.", 48, "active", 3),
    (1, "Floor lamp", "lamp", "price", 20, "Warm light, bulb included.", 7, "active", 2),
    (2, "Round brass mirror", "mirror", "price", 45, "60 cm across.", 52, "reserved", 2),
    (3, "Skateboard", "skateboard", "price", 35, "Good for cruising around the park.", 12, "active", 2),
    (4, "Small wooden desk", "desk", "price", 60, "Fits in a corner, one drawer. Easy to take apart.", 70, "active", 2),
    (5, "Moka pot (6 cups)", "mokapot", "price", 15, "", 20, "active", 1),
    (6, "Wooden stool", "stool", "free", None, "Sturdy. Free to whoever comes first.", 6, "active", 2),
    (7, "Retro toaster", "toaster", "price", 18, "Two slots, still toasts evenly.", 33, "active", 2),
    (0, "Over-ear headphones", "headphones", "price", 40, "Wired, great sound, comes with the case.", 15, "active", 2),
    (1, "Blue backpack", "backpack", "price", 22, "Laptop sleeve inside.", 90, "active", 2),
    (2, "Set of three vases", "vases", "offer", None, "Handmade, sold together.", 40, "active", 3),
    (3, "Winter boots, size 8", "boots", "price", 50, "Warm to -30. One season of use.", 11, "active", 2),
    (4, "Bookshelf", "shelf", "price", 55, "Three shelves, 90 cm tall.", 60, "reserved", 2),
    (5, "Board game night bundle", "boardgame", "price", 28, "Three games, all pieces there.", 8, "active", 2),
    (6, "Coral kettle", "kettle", "price", 14, "Stovetop, whistles loudly.", 100, "active", 1),
    (7, "Road bike (older)", "bike", "price", 120, "Steel frame, a few scratches, rides great.", 200, "sold", 2),
    (0, "Velvet armchair (green)", "armchair", "price", 70, "", 300, "sold", 1),
    (5, "Houseplant cuttings", "plant", "free", None, "Pothos and spider plant cuttings, bring a jar.", 240, "sold", 1),
]
# Tables that hold demo rows (each has an is_demo column). Children before parents.
DEMO_TABLES = ["messages", "chats", "reports", "saves", "photos", "listings"]


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    """Call from the app's main data callables: loads the demo once, unless an admin removed it."""
    if state() == "never":
        load()


def _photo(owner, art, variant, created):
    img = anvil.BlobMedia("image/svg+xml", DemoArt.svg(art, variant).encode("utf-8"), name=art + ".svg")
    return app_tables.photos.add_row(owner=owner, listing=None, key=C.token(24), image=img, thumb=img,
                                     created=created, is_demo=True)


def load():
    remove(remember=False)
    users = []
    for i, (name, email, area, lat, lng) in enumerate(DEMO_USERS):
        u = app_tables.users.get(email=email) or app_tables.users.add_row(email=email, enabled=False)
        u.update(display_name=name, is_demo=True, signed_up=C.now() - dt.timedelta(days=40 + 37 * i),
                 adult_confirmed_at=C.now(), spot_label=area, spot_lat=lat, spot_lng=lng)
        C.public_key(u)
        users.append(u)
    for who, title, art, mode, price, note, hours, status, n in DEMO_LISTINGS:
        u = users[who]
        when = C.now() - dt.timedelta(hours=hours)
        photos = [_photo(u, art, v, when) for v in range(n)]
        r = app_tables.listings.add_row(owner=u, key=C.token(10), title=title, price=float(price) if price is not None else None,
                                        price_mode=mode, note=note, status=status, area=u["spot_label"], lat=u["spot_lat"],
                                        lng=u["spot_lng"], photo_keys=[p["key"] for p in photos], created=when, bumped=when,
                                        sold_at=when + dt.timedelta(hours=20) if status == "sold" else None,
                                        views=7 + (hours * 3) % 41, hidden=False, is_demo=True)
        for p in photos:
            p["listing"] = r
    C.set_setting("demo", "loaded")
    return counts()


def remove(remember=True):
    demo_users = list(app_tables.users.search(is_demo=True))
    demo_listings = list(app_tables.listings.search(is_demo=True))
    # real rows that point at demo rows: chats with demo sellers, saves / reports of demo items
    for c in app_tables.chats.search():
        if c["is_demo"] or c["seller"] in demo_users or c["buyer"] in demo_users or c["listing"] in demo_listings:
            for m in app_tables.messages.search(chat=c):
                m.delete()
            c.delete()
    for t in (app_tables.saves, app_tables.reports):
        for x in t.search():
            if x["listing"] in demo_listings:
                x.delete()
    for name in DEMO_TABLES:
        for r in getattr(app_tables, name).search(is_demo=True):
            r.delete()
    for u in demo_users:
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    out = {"users": len(app_tables.users.search(is_demo=True))}
    for name in ["listings", "photos"]:
        out[name] = len(getattr(app_tables, name).search(is_demo=True))
    return out
