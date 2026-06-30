/* Citify.ca — Main JS */

// Dark/light theme toggle
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'light' ? 'dark' : 'light';
  html.setAttribute('data-theme', next);
  localStorage.setItem('citify-theme', next);
}

// Restore saved theme on load
(function() {
  const saved = localStorage.getItem('citify-theme');
  if (saved === 'light') document.documentElement.setAttribute('data-theme', 'light');
})();

// Initialise Leaflet map if element exists
function initMap(lat, lon, name) {
  const el = document.getElementById('citify-map');
  if (!el || !lat || !lon) return;

  const map = L.map('citify-map', { zoomControl: true, scrollWheelZoom: false }).setView([lat, lon], 15);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  const icon = L.divIcon({
    html: '<div style="background:#e94560;width:24px;height:24px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.4)"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    className: '',
  });

  L.marker([lat, lon], { icon }).addTo(map).bindPopup(`<b>${name}</b>`).openPopup();
}

// Image preview before upload
function previewImages(input, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  Array.from(input.files).forEach(file => {
    const reader = new FileReader();
    reader.onload = e => {
      const img = document.createElement('img');
      img.src = e.target.result;
      img.style.cssText = 'width:80px;height:80px;object-fit:cover;border-radius:8px;border:1px solid var(--border)';
      container.appendChild(img);
    };
    reader.readAsDataURL(file);
  });
}

// Subcategory loader based on category selection
function loadSubcategories(categoryId, selectEl) {
  if (!categoryId || !selectEl) return;
  fetch(`/api/subcategories/${categoryId}`)
    .then(r => r.json())
    .then(data => {
      selectEl.innerHTML = '<option value="">— Select subcategory —</option>';
      data.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        selectEl.appendChild(opt);
      });
    })
    .catch(() => {});
}

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });
});

// Multi-pin map for merchants with multiple locations
function initMultiMap(locations) {
  const el = document.getElementById('citify-map');
  if (!el || !locations || !locations.length) return;

  const icon = L.divIcon({
    html: '<div style="background:#e94560;width:24px;height:24px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.4)"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    className: '',
  });

  const map = L.map('citify-map', { zoomControl: true, scrollWheelZoom: false });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  const bounds = [];
  locations.forEach(function(loc) {
    if (!loc.lat || !loc.lon) return;
    const popup = loc.label
      ? `<b>${loc.label}</b>${loc.address ? '<br><span style="font-size:0.85em">' + loc.address + '</span>' : ''}`
      : (loc.address || '');
    L.marker([loc.lat, loc.lon], { icon }).addTo(map).bindPopup(popup);
    bounds.push([loc.lat, loc.lon]);
  });

  if (bounds.length === 1) {
    map.setView(bounds[0], 15);
    map.eachLayer(function(l) { if (l.openPopup) l.openPopup(); });
  } else if (bounds.length > 1) {
    map.fitBounds(bounds, { padding: [30, 30] });
  }
}

// ── Favourites ────────────────────────────────────────────────────────────────
function getFavs() {
  try { return JSON.parse(localStorage.getItem('citify_favourites') || '[]'); }
  catch { return []; }
}
function toggleFav(merchantId, btn) {
  let favs = getFavs();
  const id = parseInt(merchantId);
  if (favs.includes(id)) {
    favs = favs.filter(i => i !== id);
    btn.classList.remove('fav-active');
    btn.title = btn.dataset.add;
  } else {
    favs.push(id);
    btn.classList.add('fav-active');
    btn.title = btn.dataset.remove;
  }
  localStorage.setItem('citify_favourites', JSON.stringify(favs));
}
function initFavBtn(btn) {
  const id = parseInt(btn.dataset.merchantId);
  if (getFavs().includes(id)) {
    btn.classList.add('fav-active');
    btn.title = btn.dataset.remove;
  }
  btn.addEventListener('click', function(e) {
    e.preventDefault();
    toggleFav(id, btn);
  });
}
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.fav-btn').forEach(initFavBtn);
});

// ── Star rating widget ────────────────────────────────────────────────────────
function hoverStars(label, val) {
  const container = label.closest('.d-flex');
  const labels = container.querySelectorAll('label');
  labels.forEach(function(l) {
    const lval = parseInt(l.querySelector('i').closest('label').htmlFor.match(/star(\d+)/)[1]);
    l.style.color = lval <= val ? '#f5a623' : 'var(--text-muted)';
  });
}
function resetStars(container) {
  const checked = container.querySelector('input[type="radio"]:checked');
  const val = checked ? parseInt(checked.value) : 0;
  container.querySelectorAll('label').forEach(function(l) {
    const lval = parseInt(l.htmlFor.match(/star(\d+)/)[1]);
    l.style.color = lval <= val ? '#f5a623' : 'var(--text-muted)';
  });
}
function selectStar(label) {
  const val = parseInt(label.htmlFor.match(/star(\d+)/)[1]);
  const container = label.closest('.d-flex');
  container.querySelectorAll('label').forEach(function(l) {
    const lval = parseInt(l.htmlFor.match(/star(\d+)/)[1]);
    l.style.color = lval <= val ? '#f5a623' : 'var(--text-muted)';
  });
}
