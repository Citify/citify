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
