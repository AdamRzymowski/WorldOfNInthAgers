// Reads the "plant your banner" form submissions from the Netlify API and
// turns the ones old enough to be approved into map entries.
//
// Needs NETLIFY_API_TOKEN: a personal access token set in the project's
// environment variables (see README.md). It never reaches the browser.

const API = "https://api.netlify.com/api/v1";
const FORM_ID = "6aef0399a725d45aa1780ff6"; // community-submission
const PAGE_SIZE = 100;

// Submissions go on the map once they are this old, unless deleted or marked
// as spam in Netlify first.
export const APPROVAL_DELAY_MS = 24 * 60 * 60 * 1000;

async function api(path) {
  const token = process.env.NETLIFY_API_TOKEN;
  if (!token) throw new Error("NETLIFY_API_TOKEN is not set");
  const response = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`Netlify API ${path}: HTTP ${response.status}`);
  return response.json();
}

// Verified submissions only: spam never comes back from this endpoint.
export async function listSubmissions() {
  const all = [];
  for (let page = 1; ; page++) {
    const batch = await api(`/forms/${FORM_ID}/submissions?per_page=${PAGE_SIZE}&page=${page}`);
    all.push(...batch);
    if (batch.length < PAGE_SIZE) return all;
  }
}

export async function getSubmission(id) {
  return api(`/submissions/${encodeURIComponent(id)}`);
}

export function isApproved(submission, now = Date.now()) {
  return now - Date.parse(submission.created_at) >= APPROVAL_DELAY_MS;
}

// An uploaded file comes back as { url, filename, ... } or, in older
// submissions, as a bare URL.
export function fileUrl(value) {
  if (!value) return null;
  const url = typeof value === "string" ? value : value.url;
  return typeof url === "string" && /^https:\/\//.test(url) ? url : null;
}

function text(value, max) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

function webLink(value) {
  try {
    const url = new URL(text(value, 300));
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

// What the map shows for a submission. Only these fields are ever published:
// the address, IP address and anything else sent stay in Netlify.
export function toCommunity(submission) {
  const d = submission.data ?? {};
  const name = text(d.name, 100);
  let lat = Number(d.latitude);
  let lon = Number(d.longitude);
  const country = text(d.country, 100);
  if (!name || !country || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;

  const type = ["Club/Community", "Store", "Person"].includes(d.type) ? d.type : undefined;
  // A person's pin is rounded to about 1 km so it doesn't point at their home.
  if (type === "Person") {
    lat = Math.round(lat * 100) / 100;
    lon = Math.round(lon * 100) / 100;
  }

  const links = [];
  const invite = text(d.discord, 300); // the form allows leaving off https://
  const discord = invite && webLink(/^https?:\/\//i.test(invite) ? invite : `https://${invite}`);
  if (discord) links.push({ type: "discord", label: "Join the Discord server", url: discord });
  const whatsapp = webLink(d.whatsapp);
  if (whatsapp) links.push({ type: "whatsapp", label: "WhatsApp group", url: whatsapp });
  const facebook = webLink(d.facebook);
  if (facebook) links.push({ type: "facebook", label: name, url: facebook, title: "Facebook page" });
  const website = webLink(d.website);
  if (website) links.push({ type: "website", label: new URL(website).host, url: website });

  const community = {
    name,
    lat,
    lon,
    type,
    gamingSpace: d.gaming_space === "Yes" ? true : d.gaming_space === "No" ? false : undefined,
    description: text(d.comment, 200) || undefined,
    forumUsername: text(d.forum_username, 50) || undefined,
    discordUsername: text(d.discord_username, 38) || undefined,
    links,
    logo: fileUrl(d.logo) ? `/api/logo?id=${encodeURIComponent(submission.id)}` : undefined,
  };
  return { country, community };
}
