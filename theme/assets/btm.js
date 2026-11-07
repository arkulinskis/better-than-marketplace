/* btm.js: the marketplace's browser engines (window.BTM), reached from Python through client_code/btm.py.
   Everything else (pages, cards, lists, dialogs) is Python Forms. What stays JavaScript:
   - maps: Leaflet 1.9.4 from unpkg (loaded on demand), OpenStreetMap tiles, Nominatim search / reverse on a tap only
     (BTM.pickerMap for the spot picker dialog, BTM.areaMap for the ~1 km circle on an item page)
   - photos: shrinking on the phone before upload (BTM.shrink: 1600 px JPEG + 560 px thumbnail)
   - the share sheet / clipboard, confetti, the photo lightbox, geolocation. */
(function () {
  'use strict';
  var BTM = window.BTM = window.BTM || {};
  var HOME = { lat: 45.5088, lng: -73.5878 };  // Montréal: where the map opens when we know nothing else

  /* Listing photos are served by the app's /photo endpoint (startup.py sets APP_API; locally it's _/api). */
  BTM.apiBase = function () { return (window.APP_API || '_/api').replace(/\/$/, ''); };
  BTM.photo = function (key, thumb) {
    return key ? BTM.apiBase() + '/photo?k=' + encodeURIComponent(key) + (thumb ? '&s=t' : '') : '';
  };
  BTM.money = function (n) {
    var whole = Math.round(n) === n;
    return '$' + Number(n).toLocaleString('en-CA', { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 });
  };

  /* ---------------------------------------------------------------- maps (Leaflet, loaded only when needed) */
  var leafletP = null;
  BTM.leaflet = function () {
    if (window.L && window.L.map) return Promise.resolve(window.L);
    if (leafletP) return leafletP;
    leafletP = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = function () { window.L ? resolve(window.L) : reject(new Error('no map')); };
      s.onerror = function () { leafletP = null; reject(new Error('The map couldn\'t load.')); };
      document.head.appendChild(s);
      setTimeout(function () { if (!window.L) { leafletP = null; reject(new Error('The map is taking too long to load.')); } }, 12000);
    });
    return leafletP;
  };
  /* OpenStreetMap's own tiles (light use, normal Referer, as their tile policy asks). CARTO's free basemaps started
     answering "API key required" in Oct 2026. Dark mode inverts the tile pane in app.css. */
  function tiles(L, map) {
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
  }
  function pinIcon(L) {
    return L.divIcon({ className: '', iconSize: [34, 42], iconAnchor: [17, 40],
      html: '<svg class="bt-pin" viewBox="0 0 34 42" aria-hidden="true"><path d="M17 40s14-12.6 14-23A14 14 0 0 0 3 17c0 10.4 14 23 14 23z" fill="#ff5a36" stroke="#1e1a16" stroke-width="2.5"/>' +
        '<circle cx="17" cy="17" r="6" fill="#ffc93c" stroke="#1e1a16" stroke-width="2.5"/></svg>' });
  }
  function msg(el, text) {
    el.innerHTML = '';
    var d = document.createElement('div');
    d.className = 'bt-map-msg'; d.textContent = text;
    el.appendChild(d);
  }

  /* Nominatim: only on a tap (search or pin), never while typing, as its usage policy asks. */
  function areaName(a) {
    if (!a) return '';
    var local = a.neighbourhood || a.suburb || a.quarter || a.city_district || a.borough || '';
    var town = a.city || a.town || a.village || a.municipality || a.county || '';
    return [local, town].filter(Boolean).filter(function (v, i, all) { return all.indexOf(v) === i; }).join(', ').slice(0, 60);
  }
  BTM.reverse = function (lat, lng) {
    return fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=15&addressdetails=1&lat=' + lat + '&lon=' + lng)
      .then(function (r) { return r.json(); }).then(function (j) { return areaName(j.address); }).catch(function () { return ''; });
  };
  /* Resolves a JSON string: [{lat, lng, name, label}] (label = the full place name to show). */
  BTM.search = function (text) {
    return fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=5&q=' + encodeURIComponent(text))
      .then(function (r) { return r.json(); }).then(function (list) {
        return JSON.stringify(list.map(function (p) {
          var name = areaName(p.address) || (p.display_name || '').split(',').slice(0, 2).join(',');
          return { lat: +p.lat, lng: +p.lon, name: name.slice(0, 60), label: p.display_name || name };
        }));
      });
  };
  /* The browser's position: resolves {lat, lng}, rejects with a readable message. */
  BTM.locate = function () {
    return new Promise(function (resolve, reject) {
      if (!navigator.geolocation) { reject(new Error('This browser can\'t share its location. Search a place instead.')); return; }
      navigator.geolocation.getCurrentPosition(function (p) { resolve({ lat: p.coords.latitude, lng: p.coords.longitude }); },
        function () { reject(new Error('We couldn\'t get your location. Allow it in your browser, or search a place.')); },
        { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 });
    });
  };

  /* The spot picker's map: a draggable pin. onMove(lat, lng) whenever the pin moves by a tap or a drag.
     Returns a controller at once: setPos(lat, lng, zoom), destroy(). The map draws when Leaflet has loaded. */
  BTM.pickerMap = function (el, lat, lng, onMove) {
    var map = null, marker = null, L = null, dead = false, pending = lat != null ? { lat: lat, lng: lng, zoom: 14 } : null;
    msg(el, 'Loading the map…');
    function place(p, zoom) {
      if (!map) { pending = { lat: p.lat, lng: p.lng, zoom: zoom }; return; }
      if (!marker) marker = L.marker([p.lat, p.lng], { icon: pinIcon(L), draggable: true }).addTo(map)
        .on('dragend', function (ev) { var ll = ev.target.getLatLng(); onMove(ll.lat, ll.lng); });
      else marker.setLatLng([p.lat, p.lng]);
      if (zoom) map.setView([p.lat, p.lng], zoom);
    }
    BTM.leaflet().then(function (LL) {
      if (dead) return;
      L = LL; el.innerHTML = '';
      var start = pending || HOME;
      map = L.map(el, { scrollWheelZoom: true }).setView([start.lat, start.lng], pending ? 14 : 11);
      tiles(L, map);
      map.on('click', function (ev) { place(ev.latlng); onMove(ev.latlng.lat, ev.latlng.lng); });
      if (pending) place(pending, pending.zoom);
      setTimeout(function () { if (map) map.invalidateSize(); }, 150);
    }, function (e) { msg(el, e.message + ' Use your location or search a place instead.'); });
    return {
      setPos: function (la, ln, zoom) { place({ lat: +la, lng: +ln }, zoom || null); },
      destroy: function () { dead = true; if (map) { try { map.remove(); } catch (e) {} map = null; } }
    };
  };

  /* An item's rough area: a ~1 km circle, no exact spot. Returns {destroy}. */
  BTM.areaMap = function (el, lat, lng) {
    var map = null, dead = false;
    BTM.leaflet().then(function (L) {
      if (dead || !document.body.contains(el)) return;
      el.innerHTML = '';
      map = L.map(el, { scrollWheelZoom: false, zoomControl: true, attributionControl: true }).setView([lat, lng], 13);
      tiles(L, map);
      L.circle([lat, lng], { radius: 900, color: '#ff5a36', weight: 3, fillColor: '#ffc93c', fillOpacity: 0.35 }).addTo(map);
      setTimeout(function () { if (map) map.invalidateSize(); }, 150);
    }, function () { /* the area name is already shown in the box */ });
    return { destroy: function () { dead = true; if (map) { try { map.remove(); } catch (e) {} map = null; } } };
  };

  /* ---------------------------------------------------------------- photos: shrink on the phone before uploading */
  function drawJpeg(img, max, quality) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height, s = Math.min(1, max / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
    var g = c.getContext('2d');
    g.fillStyle = '#ffffff'; g.fillRect(0, 0, c.width, c.height);
    g.imageSmoothingQuality = 'high';
    g.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', quality);
  }
  /* Resolves {full, thumb} (JPEG data URLs) or rejects with a readable message. */
  BTM.shrink = function (file) {
    return new Promise(function (resolve, reject) {
      if (!file || !/^image\//.test(file.type || 'image/')) { reject(new Error('That file isn\'t a picture.')); return; }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        try {
          var full = drawJpeg(img, 1600, 0.82), thumb = drawJpeg(img, 560, 0.74);
          URL.revokeObjectURL(url);
          resolve({ full: full, thumb: thumb });
        } catch (e) { reject(new Error('That picture couldn\'t be read.')); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('That picture couldn\'t be read. Try a JPEG or PNG.')); };
      img.src = url;
    });
  };

  /* ---------------------------------------------------------------- share, confetti, lightbox */
  /* Resolves 'shared', 'copied' or 'manual' (Python then shows the link to copy by hand). */
  BTM.share = function (title, text, url) {
    if (navigator.share) return navigator.share({ title: title, text: text, url: url }).then(function () { return 'shared'; }, function () { return 'shared'; });
    if (navigator.clipboard) return navigator.clipboard.writeText(url).then(function () { return 'copied'; }, function () { return 'manual'; });
    return Promise.resolve('manual');
  };
  BTM.confetti = function () {
    if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var box = document.createElement('div'), colors = ['#ff5a36', '#ffc93c', '#9be7b0', '#7fb7f0', '#ffffff'];
    box.className = 'bt-confetti'; box.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < 70; i++) {
      var p = document.createElement('i');
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[i % colors.length];
      p.style.setProperty('--dx', (Math.random() * 160 - 80) + 'px');
      p.style.setProperty('--r', (Math.random() * 900 - 450) + 'deg');
      p.style.animationDuration = (1.6 + Math.random() * 1.6) + 's';
      p.style.animationDelay = Math.random() * 0.4 + 's';
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(function () { box.remove(); }, 4200);
  };
  /* A photo full screen; a click or Escape closes it and gives the focus back. */
  BTM.lightbox = function (src, alt) {
    var back = document.activeElement, box = document.createElement('div'), img = document.createElement('img');
    box.className = 'ui it-light'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', alt || 'Photo'); box.tabIndex = -1;
    img.src = src; img.alt = alt || '';
    box.appendChild(img);
    function close() { box.remove(); document.removeEventListener('keydown', key); if (back && back.focus) back.focus(); }
    function key(e) { if (e.key === 'Escape') close(); }
    box.addEventListener('click', close);
    document.addEventListener('keydown', key);
    document.body.appendChild(box);
    box.focus();
  };
})();
