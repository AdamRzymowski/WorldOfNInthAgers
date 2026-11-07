// "Street map": a real OpenStreetMap view of the open country (via Leaflet,
// loaded in index.html), in place of the painted map. Visitors can find their
// town or address and plant their banner on the exact spot.

const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
// Free address search. Its usage policy allows about one search a second,
// which a person typing an address never comes near.
const SEARCH = "https://nominatim.openstreetmap.org/search";

// getCurrent() returns the open country ({ feature, list }); getBounds() its
// mainland as [[west, south], [east, north]]; showCommunity(c) opens a card.
export function setupStreetMap({ mapWrap, join, getCurrent, getBounds, showCommunity, logoOf }) {
  const container = document.getElementById("street-map");
  const toggle = document.getElementById("view-toggle");
  const search = document.getElementById("street-search");
  const searchInput = search.querySelector("input");
  const status = document.getElementById("street-status");

  let map = null;
  let markers = null;
  let found = null; // the last address searched for, offered to the form

  const bannerIcon = L.divIcon({
    className: "street-banner",
    html: '<img src="assets/banner.webp" alt="">',
    iconSize: [46, 60],
    iconAnchor: [3, 60], // the foot of the pole
  });

  function createMap() {
    map = L.map(container, { attributionControl: false, worldCopyJump: true });
    L.control.attribution({ position: "topright", prefix: false }).addTo(map);
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);
    markers = L.layerGroup().addTo(map);
    map.on("click", (event) => {
      if (!join.isPlanting()) return;
      const { lat, lng } = event.latlng.wrap();
      const banner = L.marker(event.latlng, { icon: bannerIcon, interactive: false, keyboard: false }).addTo(map);
      join.place(banner, [lng, lat], { address: found });
    });
  }

  function drawCommunities() {
    markers.clearLayers();
    for (const community of getCurrent().list) {
      if (!Number.isFinite(community.lat) || !Number.isFinite(community.lon)) continue;
      const icon = L.divIcon({
        className: "street-marker",
        html: `<img src="${logoOf(community)}" alt="">`,
        iconSize: [40, 40],
      });
      L.marker([community.lat, community.lon], { icon, title: community.name, alt: community.name })
        .on("click", () => showCommunity(community))
        .addTo(markers);
    }
  }

  function fitCountry() {
    const [[west, south], [east, north]] = getBounds();
    // A country across the date line has its west edge east of its east edge.
    map.fitBounds([
      [south, west],
      [north, east < west ? east + 360 : east],
    ]);
  }

  function setView(street) {
    mapWrap.classList.toggle("street-view", street);
    container.hidden = !street;
    search.hidden = !street;
    toggle.setAttribute("aria-pressed", String(street));
    toggle.textContent = street ? "Painted map" : "Street map";
    if (!street) return;
    if (!map) createMap();
    map.invalidateSize();
    fitCountry();
    drawCommunities();
  }

  toggle.addEventListener("click", () => setView(container.hidden));

  search.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = searchInput.value.trim();
    if (!query) return;
    const [[west, south], [east, north]] = getBounds();
    const params = new URLSearchParams({
      q: query,
      format: "jsonv2",
      limit: "1",
      viewbox: `${west},${north},${east},${south}`, // prefer places in this country
      "accept-language": navigator.language,
    });
    status.textContent = "Searching…";
    try {
      const response = await fetch(`${SEARCH}?${params}`);
      const [place] = response.ok ? await response.json() : [];
      if (!place) {
        status.textContent = "Nothing found. Try a town name.";
        return;
      }
      found = query;
      const [s, n, w, e] = place.boundingbox.map(Number);
      map.fitBounds([
        [s, w],
        [n, e],
      ], { maxZoom: 17 });
      status.textContent = join.isPlanting() ? "Now click the exact spot." : "";
    } catch (err) {
      console.warn("Address search failed", err);
      status.textContent = "Search isn't working right now. Move the map by hand instead.";
    }
  });

  return {
    isOn: () => !container.hidden,
    // Back to the painted map, e.g. when another country opens.
    reset() {
      found = null;
      searchInput.value = "";
      status.textContent = "";
      setView(false);
    },
  };
}
