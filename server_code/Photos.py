"""Serves listing photos: <app>/_/api/photo?k=<key>[&s=t]  (s=t: the small thumbnail).

Keys are 24 random characters, so a photo can only be found through its listing. Photos not attached to a
listing yet (still being posted) are never served: the seller's phone shows its own copy meanwhile.
Pictures never change under a key, so browsers may keep them for a year.
"""
import anvil.server
from anvil.tables import app_tables


@anvil.server.http_endpoint("/photo")
def photo(k=None, s=None, **kw):
    p = app_tables.photos.get(key=k) if isinstance(k, str) and 10 <= len(k) <= 40 else None
    if p is None or p["listing"] is None:
        return anvil.server.HttpResponse(404, "Not found")
    media = p["thumb"] if s == "t" and p["thumb"] is not None else p["image"]
    return anvil.server.HttpResponse(200, media, headers={"Cache-Control": "public, max-age=31536000, immutable",
                                                         "Content-Type": media.content_type})
