// "Add community, store or point of contact on the map": plant a banner on
// the country map, then fill in a form that goes to Netlify Forms.

const MAX_LOGO_BYTES = 15 * 1024 * 1024; // the original; what's sent is the small miniature
const MINIATURE = 256; // px, square: the size community markers are drawn from
// Everything in "How can people reach you?": at least one is needed.
const CONTACTS = ["discord", "whatsapp", "facebook", "website", "forum_username", "discord_username"];
const MAX_LENGTH = { name: 100, address: 100, discord: 50, forum_username: 50, discord_username: 38, website: 200, comment: 200 };
const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];
// An invite link: discord.gg/<code> or discord.com/invite/<code>, with or without https://.
// 2–32 of letters, digits, _ and . (Discord's own rule), with an optional
// leading @ and the old #1234 tag still accepted.
const DISCORD_USERNAME = /^@?[a-z0-9_.]{2,32}(#\d{4})?$/i;
const DISCORD_INVITE = /^(https?:\/\/)?(www\.)?(discord\.gg|discord(app)?\.com\/invite)\/[a-z0-9-]{2,32}\/?$/i;
// Free address search (OpenStreetMap), as on the Real World View.
const SEARCH = "https://nominatim.openstreetmap.org/search";

// countrySvg/mapLayer: the country view's d3 selections. getCurrent() returns
// the open country: { feature, fromMap(x, y) -> [lon, lat], contains(x, y) },
// both in mapLayer coordinates.
export function setupJoin({ countrySvg, mapLayer, mapWrap, getCurrent, getCanvasWidth }) {
  const addButton = document.getElementById("add-button");
  const hint = document.getElementById("plant-hint");
  const cursor = document.getElementById("banner-cursor");
  const formDialog = document.getElementById("join-dialog");
  const form = document.getElementById("join-form");
  const errorEl = document.getElementById("join-error");
  const done = document.getElementById("join-done");
  const submit = document.getElementById("join-submit");
  const logoInput = document.getElementById("join-logo");
  const logoPreview = document.getElementById("join-logo-preview");

  let planting = false;
  let planted = null; // the banner placed on the map, while the form is open

  function start() {
    if (!getCurrent()) return;
    planting = true;
    mapWrap.classList.add("planting");
    hint.hidden = false;
    addButton.setAttribute("aria-pressed", "true");
  }

  function stop() {
    planting = false;
    mapWrap.classList.remove("planting");
    hint.hidden = true;
    cursor.hidden = true;
    addButton.setAttribute("aria-pressed", "false");
  }

  function removePlanted() {
    planted?.remove();
    planted = null;
  }

  addButton.addEventListener("click", () => (planting ? stop() : start()));
  hint.querySelector("[data-plant-cancel]").addEventListener("click", stop);

  // The waving banner follows the pointer in place of the cursor, over the
  // painted map and the street map alike.
  d3.select(mapWrap)
    .on("pointermove.join", (event) => {
      if (!planting || event.pointerType === "touch") return;
      const box = mapWrap.getBoundingClientRect();
      cursor.hidden = false;
      cursor.style.left = `${event.clientX - box.left}px`;
      cursor.style.top = `${event.clientY - box.top}px`;
    })
    .on("pointerleave.join", () => (cursor.hidden = true));

  countrySvg.on("click.join", (event) => {
    if (!planting) return;
    const current = getCurrent();
    const [x, y] = d3.pointer(event, mapLayer.node());
    if (!current.contains(x, y)) {
      flashHint(`Plant it inside ${current.feature.properties.name}`);
      return;
    }
    stop();
    plantAt(x, y);
    openForm(current, current.fromMap(x, y));
  });

  function flashHint(text) {
    const label = hint.querySelector("span");
    label.textContent = text;
    hint.classList.add("warn");
    setTimeout(() => {
      label.textContent = "Plant your banner on the map!";
      hint.classList.remove("warn");
    }, 1800);
  }

  function plantAt(x, y) {
    removePlanted();
    const h = getCanvasWidth() * 0.08;
    const w = h * (229 / 300);
    // The foot of the pole (11.5, 300 of the 229 x 300 image) stands on the chosen spot.
    planted = mapLayer
      .append("image")
      .attr("class", "planted-banner")
      .attr("href", "assets/banner.webp")
      .attr("x", x - (11.5 / 229) * w)
      .attr("y", y - h)
      .attr("width", w)
      .attr("height", h);
  }

  /* ----------------------------------------------------------------- form */

  // A banner planted on another view (the street map): `banner` is whatever
  // marks the spot there, removed again when the form closes.
  function place(banner, lonLat, { address } = {}) {
    stop();
    removePlanted();
    planted = banner;
    openForm(getCurrent(), lonLat);
    if (address && address.length <= form.elements.address.maxLength) form.elements.address.value = address;
  }

  function openForm(current, [lon, lat]) {
    form.reset();
    clearRequired();
    resetLogo();
    errorEl.hidden = true;
    done.hidden = true;
    form.classList.remove("sent");
    submit.disabled = false;
    form.elements.country.value = current.feature.properties.name;
    form.elements.latitude.value = lat.toFixed(4);
    form.elements.longitude.value = lon.toFixed(4);
    formDialog.showModal();
    form.elements.name.focus();
  }

  function closeForm() {
    formDialog.close();
  }

  formDialog.addEventListener("close", removePlanted);
  // Only the ×, Cancel and "Back to the map" close the form, so a stray
  // click outside it or Escape doesn't lose what was typed.
  formDialog.addEventListener("click", (event) => {
    if (event.target.closest("[data-join-close]")) closeForm();
  });
  formDialog.addEventListener("cancel", (event) => event.preventDefault());

  let miniature = null; // the logo as sent: a small square image made from the upload

  function resetLogo() {
    miniature = null;
    logoPreview.replaceChildren("+");
    logoPreview.classList.remove("has-image");
  }

  logoInput.addEventListener("change", async () => {
    const file = logoInput.files[0];
    resetLogo();
    logoInput.setCustomValidity("");
    errorEl.hidden = true;
    if (!file) return;
    if (!LOGO_TYPES.includes(file.type)) {
      logoInput.setCustomValidity("The logo must be a PNG, JPEG, WebP or GIF image.");
    } else if (file.size > MAX_LOGO_BYTES) {
      logoInput.setCustomValidity("That image is too large (15 MB at most).");
    } else {
      try {
        miniature = await makeMiniature(file);
      } catch (err) {
        console.warn("Could not read the logo", err);
        logoInput.setCustomValidity("That image couldn't be read. Try a PNG or JPEG.");
      }
    }
    if (!miniature) return showError(logoInput.validationMessage);
    const img = document.createElement("img");
    img.alt = "";
    img.src = URL.createObjectURL(miniature);
    logoPreview.replaceChildren(img);
    logoPreview.classList.add("has-image");
  });

  // The labelled block a field belongs to: its label, or the whole fieldset
  // for the contacts and the Yes/No choice.
  function sectionOf(field) {
    return field.closest("fieldset") ?? field.closest(".field");
  }

  // The note goes right under the section's heading (a fieldset's legend),
  // so it's the heading that reads as required, not the last field in it.
  function markRequired(section) {
    section.classList.add("missing");
    const note = document.createElement("p");
    note.className = "required-note";
    note.textContent = "This section is required";
    const legend = section.querySelector(":scope > legend");
    if (legend) legend.after(note);
    else section.append(note);
  }

  function clearRequired(section) {
    for (const el of section ? [section] : form.querySelectorAll(".missing")) {
      el.classList.remove("missing");
      el.querySelector(".required-note")?.remove();
    }
  }

  // Filling in a marked section clears its note straight away.
  form.addEventListener("input", (event) => {
    const section = event.target.closest(".missing");
    if (section) clearRequired(section);
  });

  function showError(message, field) {
    errorEl.textContent = message;
    errorEl.hidden = false;
    field?.focus();
  }

  function validate() {
    const { elements } = form;
    for (const key of ["name", "address", "comment", ...CONTACTS]) elements[key].value = elements[key].value.trim();
    // Every required section left empty gets its own red note at once.
    const missing = [
      [!elements.name.value, elements.name],
      [!elements.type.value, elements.type],
      [!elements.gaming_space.value, elements.gaming_space[0]],
      [!CONTACTS.some((key) => elements[key].value), elements.discord],
    ].filter(([empty]) => empty).map(([, field]) => field);
    clearRequired();
    for (const field of missing) markRequired(sectionOf(field));
    if (missing.length) {
      return showError("Some required sections are empty: they're marked in red below.", missing[0]), false;
    }
    for (const [key, max] of Object.entries(MAX_LENGTH)) {
      if (elements[key].value.length > max) {
        const label = { name: "The name", address: "The address", forum_username: "The T9A forum username", discord_username: "The Discord username", website: "The website", comment: "The extra comment", discord: "The Discord link" }[key];
        return showError(`${label} can be at most ${max} characters.`, elements[key]), false;
      }
    }
    if (elements.discord.value && !DISCORD_INVITE.test(elements.discord.value)) {
      return showError("The Discord link should be an invite, like https://discord.gg/abc123.", elements.discord), false;
    }
    if (elements.discord_username.value && !DISCORD_USERNAME.test(elements.discord_username.value)) {
      return showError("A Discord username has only letters, numbers, _ and . (like klub_gargulec).", elements.discord_username), false;
    }
    if (elements.website.value) {
      const url = webUrl(elements.website.value);
      if (!url) return showError("The website should be a link, like https://example.com.", elements.website), false;
      elements.website.value = url;
    }
    if (elements.facebook.value) {
      const url = webUrl(elements.facebook.value);
      if (!url) return showError("Facebook should be a link, like https://www.facebook.com/yourgroup.", elements.facebook), false;
      elements.facebook.value = url;
    }
    if (!logoInput.checkValidity()) return showError(logoInput.validationMessage, logoInput), false;
    errorEl.hidden = true;
    return true;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!validate()) return;
    submit.disabled = true;
    submit.textContent = "Planting…";
    try {
      await pinToAddress();
      const data = new FormData(form);
      data.delete("logo");
      if (miniature) data.set("logo", miniature, `${slug(form.elements.name.value)}-logo.${miniature.type.split("/")[1]}`);
      const response = await fetch(form.getAttribute("action") ?? "/", { method: "POST", body: data });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      form.classList.add("sent");
      done.hidden = false;
      done.querySelector("button").focus();
    } catch (err) {
      console.warn("Submission failed", err);
      showError("Sorry, that didn't go through. Please try again in a moment.");
      submit.disabled = false;
    } finally {
      submit.textContent = "Ready! Plant my Banner!";
    }
  });

  // The banner planted by hand only roughly marks the spot: a given address,
  // when it can be found inside the country, decides the location instead.
  // pin_from tells the review which one was used.
  async function pinToAddress() {
    const { elements } = form;
    elements.pin_from.value = "map";
    const address = elements.address.value.trim();
    if (!address) return;
    const lonLat = await findAddress(address, getCurrent().feature);
    if (!lonLat) return;
    elements.longitude.value = lonLat[0].toFixed(4);
    elements.latitude.value = lonLat[1].toFixed(4);
    elements.pin_from.value = "address";
  }

  return { start, stop, place, isPlanting: () => planting, reset: () => (stop(), removePlanted()) };
}

// [lon, lat] of the address, or null when it isn't found in the country or
// the search doesn't answer in time (the hand-planted spot is kept then).
async function findAddress(address, feature) {
  const params = new URLSearchParams({
    q: `${address}, ${feature.properties.name}`,
    format: "jsonv2",
    limit: "1",
    "accept-language": navigator.language,
  });
  try {
    const response = await fetch(`${SEARCH}?${params}`, { signal: AbortSignal.timeout(6000) });
    const [place] = response.ok ? await response.json() : [];
    const lonLat = place && [Number(place.lon), Number(place.lat)];
    return lonLat && lonLat.every(Number.isFinite) && d3.geoContains(feature, lonLat) ? lonLat : null;
  } catch (err) {
    console.warn("Address search failed", err);
    return null;
  }
}

// Scales the logo to fit a MINIATURE-pixel square (transparent around it, so
// wide logos aren't cropped) and trims it to a small WebP, or PNG where the
// browser can't write WebP.
async function makeMiniature(file) {
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = MINIATURE;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  const scale = MINIATURE / Math.max(bitmap.width, bitmap.height);
  const w = bitmap.width * scale;
  const h = bitmap.height * scale;
  ctx.drawImage(bitmap, (MINIATURE - w) / 2, (MINIATURE - h) / 2, w, h);
  bitmap.close();
  const encode = (type) => new Promise((resolve) => canvas.toBlob(resolve, type, 0.9));
  const webp = await encode("image/webp");
  return webp?.type === "image/webp" ? webp : encode("image/png");
}

function slug(text) {
  return text.toLowerCase().normalize("NFKD").replace(/[^\w]+/g, "-").replace(/^-|-$/g, "") || "community";
}

// The address as a full http(s) link, adding https:// when it was left off,
// or null when it isn't a web address.
function webUrl(value) {
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`);
    return /^https?:$/.test(url.protocol) && /\.[a-z]{2,}$/i.test(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}
