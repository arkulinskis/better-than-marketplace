"""Drawn "photos" for the demo listings: simple sticker-style SVG pictures of everyday things (4:5, 400x500).

svg(name, variant): variant 0 = the whole thing, 1 = a close-up, 2 = from the other side on another backdrop.
Only demo content uses SVG; members' photos are always JPEG / PNG / WebP (Selling._image).
"""
import re

INK = "#1E1A16"
BACKDROPS = ["#FFE3D9", "#FFF1C7", "#DDEFE3", "#DCE8FA", "#F3E1F5", "#FDE7C8", "#E6E1F7", "#D9F1F0"]


def _a(extra=""):
    """The ink outline attributes, with any of them overridden by `extra` (an attribute may appear only once in SVG)."""
    attrs = {"stroke": INK, "stroke-width": "6", "stroke-linejoin": "round", "stroke-linecap": "round"}
    for k, v in re.findall(r'([a-z-]+)="([^"]*)"', extra):
        attrs[k] = v
    return " ".join('%s="%s"' % kv for kv in attrs.items())


def _r(x, y, w, h, fill, rx=0, extra=""):
    return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" %s/>' % (x, y, w, h, rx, fill, _a(extra))


def _c(x, y, r, fill):
    return '<circle cx="%s" cy="%s" r="%s" fill="%s" %s/>' % (x, y, r, fill, _a())


def _e(x, y, rx, ry, fill, extra=""):
    return '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s" %s/>' % (x, y, rx, ry, fill, _a(extra))


def _p(d, fill="none", extra=""):
    return '<path d="%s" fill="%s" %s/>' % (d, fill, _a(extra))


def _l(x1, y1, x2, y2, color=INK, w=6):
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" stroke-linecap="round"/>' % (x1, y1, x2, y2, color, w)


ART = {
    "armchair": lambda: (_r(112, 130, 176, 180, "#FFC93C", 46) + _r(96, 268, 208, 74, "#F5AE1E", 26) +
                         _r(66, 214, 62, 140, "#FFC93C", 30) + _r(272, 214, 62, 140, "#FFC93C", 30) +
                         _l(108, 354, 98, 410, INK, 10) + _l(292, 354, 302, 410, INK, 10) +
                         _p("M150 170 q50 30 100 0", extra='opacity=".35"')),
    "bike": lambda: (_c(118, 330, 72, "none") + _c(292, 330, 72, "none") + _c(118, 330, 8, INK) + _c(292, 330, 8, INK) +
                     '<path d="M118 330 L188 330 L262 228 L168 228 Z M188 330 L158 206 M262 228 L292 330" fill="none" '
                     'stroke="#FF5A36" stroke-width="13" stroke-linejoin="round" stroke-linecap="round"/>' +
                     _p("M188 330 L118 330 L168 228 L262 228 L188 330 M158 206 L188 330 M262 228 L292 330") +
                     _r(136, 194, 52, 16, INK, 8) + _p("M262 228 L270 196 Q292 186 304 204", extra='stroke-width="9"')),
    "plant": lambda: (_p("M200 330 C190 260 150 230 108 214", extra='stroke-width="7"') +
                      _p("M200 330 C206 250 236 200 282 178", extra='stroke-width="7"') +
                      _p("M200 330 C200 260 196 200 198 132", extra='stroke-width="7"') +
                      _p("M108 214 C60 170 92 110 150 132 C190 150 170 220 108 214 Z", "#3FA34D") +
                      _p("M282 178 C330 130 360 210 312 238 C276 258 250 214 282 178 Z", "#47B356") +
                      _p("M198 132 C150 90 190 40 230 70 C262 96 240 150 198 132 Z", "#2F8F3F") +
                      _p("M130 160 l18 10 M150 146 l10 18 M300 200 l-16 10 M214 86 l-6 18", extra='stroke="#DDEFE3" stroke-width="5"') +
                      _p("M146 330 L254 330 L240 410 L160 410 Z", "#D9774B") + _r(138, 318, 124, 24, "#E58A5E", 8)),
    "guitar": lambda: (_r(188, 56, 24, 190, "#7A4B2A", 6) + _r(178, 30, 44, 50, "#5B3820", 10) +
                       _c(200, 252, 58, "#E39B4A") + _c(200, 338, 78, "#E39B4A") +
                       '<rect x="150" y="226" width="100" height="70" fill="#E39B4A"/>' +
                       _c(200, 300, 22, INK) + _r(168, 360, 64, 14, "#5B3820", 5) +
                       _l(194, 60, 194, 366, "#FFF7EC", 2) + _l(200, 60, 200, 366, "#FFF7EC", 2) + _l(206, 60, 206, 366, "#FFF7EC", 2)),
    "camera": lambda: (_r(78, 196, 244, 156, "#3A332D", 20) + _r(78, 196, 244, 44, "#C9C2B8", 20) +
                       _r(110, 168, 60, 34, "#C9C2B8", 8) + _r(250, 176, 44, 26, "#3A332D", 6) +
                       _c(200, 284, 62, "#C9C2B8") + _c(200, 284, 44, "#2A2420") + _c(200, 284, 26, "#7FB7F0") +
                       _c(188, 272, 7, "#FFFFFF") + _c(296, 222, 9, "#FF5A36")),
    "books": lambda: (_r(96, 340, 210, 52, "#FF5A36", 8) + _r(116, 290, 180, 50, "#3F7FD9", 8) +
                      _r(84, 240, 214, 50, "#FFC93C", 8, 'transform="rotate(-3 190 265)"') + _r(124, 196, 168, 46, "#3FA34D", 8) +
                      _l(112, 366, 290, 366, "#FFF7EC", 4) + _l(134, 315, 280, 315, "#FFF7EC", 4) + _l(140, 219, 276, 219, "#FFF7EC", 4)),
    "sneakers": lambda: (_p("M70 360 C70 300 110 250 150 246 L190 300 C230 320 300 320 330 340 C350 352 346 380 330 384 L84 384 C74 384 70 374 70 360 Z", "#FFFFFF") +
                         _p("M70 360 L346 360 L346 384 L84 384 Z", "#FF5A36") +
                         _p("M150 246 L176 280 M164 266 L200 250 M178 284 L214 268", extra='stroke-width="5"') +
                         _p("M232 322 C256 300 290 312 300 330", "#3F7FD9")),
    "teapot": lambda: (_p("M110 300 C110 230 290 230 290 300 C290 360 250 386 200 386 C150 386 110 360 110 300 Z", "#5FB7A8") +
                       _p("M110 290 C70 280 60 240 80 230", extra='stroke-width="12"') +
                       _p("M290 270 C340 260 350 330 300 340", extra='stroke-width="12"') +
                       _e(200, 236, 62, 16, "#4AA595") + _c(200, 214, 12, "#FFC93C") +
                       _p("M140 300 q60 24 120 0", extra='opacity=".35"')),
    "turntable": lambda: (_r(64, 206, 272, 168, "#C08A55", 18) + _r(64, 344, 272, 30, "#A8733F", 12) +
                          _c(180, 284, 64, "#1E1A16") + _c(180, 284, 40, "#3A332D") + _c(180, 284, 16, "#FF5A36") +
                          _p("M300 228 L300 300 L232 322", extra='stroke-width="8"') + _c(300, 228, 12, "#C9C2B8") +
                          _r(276, 330, 40, 10, "#FFC93C", 4)),
    "lamp": lambda: (_p("M128 86 L272 86 L314 196 L86 196 Z", "#FFC93C") + _l(200, 196, 200, 392, INK, 10) +
                     _e(200, 398, 70, 14, "#3A332D") + _p("M160 196 q40 30 80 0", extra='opacity=".3"') +
                     '<path d="M120 216 L90 260 M280 216 L310 260 M200 220 L200 252" stroke="#FFC93C" stroke-width="6" stroke-linecap="round" opacity=".7"/>'),
    "mirror": lambda: (_c(200, 236, 132, "#E3B04B") + _c(200, 236, 108, "#CFE6F7") +
                       _p("M140 220 L196 164 M150 260 L226 184", extra='stroke="#FFFFFF" stroke-width="12" opacity=".9"') +
                       _l(200, 368, 200, 396, INK, 8)),
    "skateboard": lambda: ('<g transform="rotate(-18 200 260)">' + _r(60, 230, 280, 60, "#FF5A36", 30) +
                           _p("M110 246 l180 0", extra='stroke="#FFC93C" stroke-width="10"') +
                           _c(110, 304, 18, "#FFC93C") + _c(150, 304, 18, "#FFC93C") + _c(250, 304, 18, "#FFC93C") +
                           _c(290, 304, 18, "#FFC93C") + '</g>'),
    "desk": lambda: (_r(54, 196, 292, 30, "#C08A55", 8) + _r(224, 226, 100, 110, "#D9A46D", 6) +
                     _l(226, 280, 322, 280, INK, 5) + _c(274, 254, 5, INK) + _c(274, 308, 5, INK) +
                     _l(76, 226, 76, 400, INK, 12) + _l(316, 336, 316, 400, INK, 12) + _l(236, 336, 236, 400, INK, 12) +
                     _r(110, 150, 70, 46, "#3F7FD9", 6) + _r(196, 166, 10, 30, "#3FA34D", 4)),
    "mokapot": lambda: (_p("M140 400 L164 290 L236 290 L260 400 Z", "#C9C2B8") + _r(150, 272, 100, 26, "#8D867D", 6) +
                        _p("M156 272 L176 170 L224 170 L244 272 Z", "#D9D3CA") + _p("M168 170 L184 132 L216 132 L232 170 Z", "#C9C2B8") +
                        _c(200, 124, 10, INK) + _p("M244 200 C292 200 296 266 250 270", extra='stroke-width="12"') +
                        _p("M176 170 L150 160", extra='stroke-width="8"')),
    "stool": lambda: (_e(200, 196, 112, 30, "#E39B4A") + _p("M88 196 L88 214 C88 232 312 232 312 214 L312 196", "#C47B34") +
                      _l(122, 226, 92, 400, INK, 12) + _l(278, 226, 308, 400, INK, 12) + _l(200, 232, 200, 404, INK, 12) +
                      _l(110, 330, 290, 330, INK, 8)),
    "toaster": lambda: (_r(86, 216, 228, 170, "#9ED3E3", 46) + _r(130, 186, 50, 60, "#F2C77F", 10) + _r(220, 196, 50, 50, "#F2C77F", 10) +
                        _r(86, 216, 228, 40, "#9ED3E3", 20) + _l(140, 236, 170, 236) + _l(230, 236, 260, 236) +
                        _r(306, 280, 30, 14, INK, 6) + _c(200, 330, 14, "#FF5A36")),
    "headphones": lambda: (_p("M110 300 C100 150 300 150 290 300", extra='stroke-width="16"') +
                           _r(84, 262, 56, 110, "#FF5A36", 26) + _r(260, 262, 56, 110, "#FF5A36", 26) +
                           _r(104, 280, 22, 74, "#1E1A16", 10) + _r(274, 280, 22, 74, "#1E1A16", 10)),
    "backpack": lambda: (_r(112, 120, 176, 260, "#3F7FD9", 54) + _r(140, 270, 120, 90, "#5B95E6", 22) +
                         _p("M160 120 C160 80 240 80 240 120", extra='stroke-width="10"') + _l(160, 296, 240, 296, INK, 5) +
                         _r(168, 180, 64, 22, "#FFC93C", 10)),
    "vases": lambda: (_p("M98 400 C70 340 110 300 104 260 L140 260 C134 300 174 340 146 400 Z", "#FF5A36") +
                      _p("M176 400 C140 330 160 250 186 220 L186 160 L214 160 L214 220 C240 250 260 330 224 400 Z", "#5FB7A8") +
                      _p("M262 400 C250 360 250 320 276 300 L276 280 L302 280 L302 300 C328 320 328 360 316 400 Z", "#FFC93C") +
                      _p("M188 290 q12 10 24 0 M188 320 q12 10 24 0", extra='stroke-width="4" opacity=".6"')),
    "boots": lambda: (_p("M90 160 L170 160 L172 300 C220 300 250 320 250 360 L250 392 L90 392 Z", "#8A5A3B") +
                      _p("M80 150 L180 150 L180 196 L80 196 Z", "#EFE6DA") + _p("M90 370 L250 370 L250 392 L90 392 Z", INK) +
                      _p("M210 200 L290 200 L292 320 C330 320 350 340 350 370 L350 392 L210 392 Z", "#A8733F") +
                      _p("M200 190 L300 190 L300 234 L200 234 Z", "#EFE6DA") + _p("M210 370 L350 370 L350 392 L210 392 Z", INK)),
    "shelf": lambda: (_r(96, 76, 208, 324, "#E8C9A0", 8) + _l(96, 180, 304, 180) + _l(96, 286, 304, 286) +
                      _r(116, 112, 18, 66, "#FF5A36", 3) + _r(138, 120, 18, 58, "#3F7FD9", 3) + _r(160, 106, 18, 72, "#FFC93C", 3) +
                      _c(250, 150, 24, "#3FA34D") + _r(120, 230, 70, 54, "#5FB7A8", 6) + _r(212, 220, 18, 64, "#E39B4A", 3) +
                      _r(234, 232, 18, 52, "#3A332D", 3) + _r(140, 330, 120, 50, "#FFF1C7", 6)),
    "boardgame": lambda: ('<g transform="rotate(-8 200 280)">' + _r(84, 180, 232, 190, "#FFC93C", 12) +
                          _r(108, 204, 184, 142, "#FFF7EC", 6) +
                          "".join(_c(132 + 34 * i, 236 + 36 * j, 11, ["#FF5A36", "#3F7FD9", "#3FA34D"][(i + j) % 3])
                                  for i in range(5) for j in range(3)) + '</g>'),
    "kettle": lambda: (_p("M120 390 L136 236 C140 200 260 200 264 236 L280 390 Z", "#FF8A65") +
                       _p("M160 210 C160 150 240 150 240 210", extra='stroke-width="12"') +
                       _p("M264 260 L320 222 L314 250 L276 300", "#FF8A65") + _r(118, 370, 164, 22, INK, 8) +
                       _c(200, 300, 16, "#FFF7EC")),
}

NAMES = sorted(ART)


def svg(name, variant=0):
    body = ART[name]()
    bg = BACKDROPS[(NAMES.index(name) + 3 * variant) % len(BACKDROPS)]
    if variant == 1:
        body = '<g transform="translate(200 250) scale(1.55) translate(-200 -260)">%s</g>' % body
    elif variant == 2:
        body = '<g transform="translate(400 0) scale(-1 1)">%s</g>' % body
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500" width="400" height="500">'
            '<rect width="400" height="500" fill="%s"/><rect y="404" width="400" height="96" fill="#000" opacity=".06"/>'
            '<ellipse cx="200" cy="406" rx="150" ry="14" fill="#000" opacity=".12"/>%s</svg>' % (bg, body))
