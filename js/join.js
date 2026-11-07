// "Add community, store or point of contact on the map": plant a banner on
// the country map, then fill in a form that goes to Netlify Forms.

const MAX_LOGO_BYTES = 15 * 1024 * 1024; // the original; what's sent is the small miniature
const MINIATURE = 256; // px, square: the size community markers are drawn from
const CONTACTS = ["discord", "email", "whatsapp", "facebook"];

// countrySvg/mapLayer: the country view's d3 selections. getCurrent() returns
// the open country: { feature, fromMap(x, y) -> [lon, lat], contains(x, y) },
// both in mapLayer coordinates.
export function setupJoin({ countrySvg, mapLayer, mapWrap, getCurrent, getCanvasWidth }) {
  const addButton = document.getElementById("add-button");
  const hint = document.getElementById("plant-hint");
  const cursor = document.getElementById("banner-cursor");
  const formDialog = document.getElementById("join-dialog");
  const form = document.getElementById("join-form");
  const where = document.getElementById("join-where");
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

  // The waving banner follows the pointer in place of the cursor.
  countrySvg
    .on("pointermove.join", (event) => {
      if (!planting || event.pointerType === "touch") return;
      const box = mapWrap.getBoundingClientRect();
      cursor.hidden = false;
      cursor.style.left = `${event.clientX - box.left}px`;
      cursor.style.top = `${event.clientY - box.top}px`;
    })
    .on("pointerleave.join", () => (cursor.hidden = true))
    .on("click.join", (event) => {
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
    const h = getCanvasWidth() * 0.07;
    const w = h * 0.75;
    // The foot of the pole (8, 78 of 60 x 80) stands on the chosen spot.
    planted = mapLayer
      .append("use")
      .attr("class", "planted-banner")
      .attr("href", "#war-banner")
      .attr("x", x - (8 / 60) * w)
      .attr("y", y - (78 / 80) * h)
      .attr("width", w)
      .attr("height", h);
  }

  /* ----------------------------------------------------------------- form */

  function openForm(current, [lon, lat]) {
    form.reset();
    resetLogo();
    errorEl.hidden = true;
    done.hidden = true;
    form.classList.remove("sent");
    submit.disabled = false;
    const country = current.feature.properties.name;
    form.elements.country.value = country;
    form.elements.latitude.value = lat.toFixed(4);
    form.elements.longitude.value = lon.toFixed(4);
    where.textContent = `In ${country}, at ${formatCoord(lat, "N", "S")}, ${formatCoord(lon, "E", "W")}`;
    formDialog.showModal();
    form.elements.name.focus();
  }

  function closeForm() {
    formDialog.close();
  }

  formDialog.addEventListener("close", removePlanted);
  formDialog.addEventListener("click", (event) => {
    if (event.target === formDialog || event.target.closest("[data-join-close]")) closeForm();
  });

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
    if (!file.type.startsWith("image/")) {
      logoInput.setCustomValidity("Please choose an image file.");
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

  function showError(message, field) {
    errorEl.textContent = message;
    errorEl.hidden = false;
    field?.focus();
  }

  function validate() {
    const { elements } = form;
    for (const key of ["name", ...CONTACTS]) elements[key].value = elements[key].value.trim();
    if (!elements.name.value) return showError("Please give a name.", elements.name), false;
    if (!CONTACTS.some((key) => elements[key].value)) {
      return showError("Add at least one way to reach you: Discord, email, WhatsApp or Facebook.", elements.discord), false;
    }
    if (elements.email.value && !elements.email.checkValidity()) {
      return showError("That email address doesn't look right.", elements.email), false;
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
      submit.textContent = "Plant banner";
    }
  });

  return { start, stop, isPlanting: () => planting, reset: () => (stop(), removePlanted()) };
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

function formatCoord(value, positive, negative) {
  return `${Math.abs(value).toFixed(2)}° ${value >= 0 ? positive : negative}`;
}
