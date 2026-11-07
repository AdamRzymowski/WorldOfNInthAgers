// "Add community, store or point of contact on the map": plant a banner on
// the country map, then fill in a form that goes to Netlify Forms.

const MAX_LOGO_BYTES = 2 * 1024 * 1024;
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

  function resetLogo() {
    logoPreview.replaceChildren("+");
    logoPreview.classList.remove("has-image");
  }

  logoInput.addEventListener("change", () => {
    const file = logoInput.files[0];
    resetLogo();
    logoInput.setCustomValidity("");
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      logoInput.setCustomValidity("Please choose an image file.");
    } else if (file.size > MAX_LOGO_BYTES) {
      logoInput.setCustomValidity("The logo is too large (2 MB at most).");
    } else {
      const img = document.createElement("img");
      img.alt = "";
      img.src = URL.createObjectURL(file);
      img.onload = () => URL.revokeObjectURL(img.src);
      logoPreview.replaceChildren(img);
      logoPreview.classList.add("has-image");
      return;
    }
    showError(logoInput.validationMessage);
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
      const response = await fetch(form.getAttribute("action") ?? "/", { method: "POST", body: new FormData(form) });
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

function formatCoord(value, positive, negative) {
  return `${Math.abs(value).toFixed(2)}° ${value >= 0 ? positive : negative}`;
}
