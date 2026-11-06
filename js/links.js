// How each kind of contact in communities.json is labelled and drawn.
// Add a new type here and it can be used as "type" in any link.

const brand = (slug) => `https://cdn.jsdelivr.net/npm/simple-icons@11.0.0/icons/${slug}.svg`;
const glyph = (body) =>
  `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
  )}`;

const TYPES = {
  discord: { label: "Discord", color: "#5865F2", icon: brand("discord") },
  messenger: { label: "Messenger", color: "#0866FF", icon: brand("messenger") },
  facebook: { label: "Facebook group", color: "#0866FF", icon: brand("facebook") },
  whatsapp: { label: "WhatsApp", color: "#25D366", icon: brand("whatsapp") },
  telegram: { label: "Telegram", color: "#26A5E4", icon: brand("telegram") },
  instagram: { label: "Instagram", color: "#E4405F", icon: brand("instagram") },
  youtube: { label: "YouTube", color: "#FF0000", icon: brand("youtube") },
  website: {
    label: "Website",
    color: "#7a4a1c",
    icon: glyph('<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/>'),
  },
  email: {
    label: "Email",
    color: "#7a4a1c",
    icon: glyph('<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 6-10 7L2 6"/>'),
  },
  contact: {
    label: "Contact",
    color: "#7a4a1c",
    icon: glyph('<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'),
  },
  link: {
    label: "Link",
    color: "#7a4a1c",
    icon: glyph('<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>'),
  },
};

export function linkInfo(type) {
  return TYPES[String(type).toLowerCase()] ?? TYPES.link;
}

// Only ever link to web pages or email, never javascript: or other schemes.
export function safeUrl(link, info) {
  let raw = link.url;
  if (!raw && info === TYPES.email && link.label?.includes("@")) raw = `mailto:${link.label}`;
  if (!raw) return null;
  try {
    const url = new URL(raw, location.href);
    return ["http:", "https:", "mailto:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
