// GET /api/communities: the form submissions approved so far (older than a
// day), in the same shape as data/communities.json. The site merges them with
// that file, so new communities appear without a deploy.
import { listSubmissions, isApproved, toCommunity } from "../lib/submissions.mjs";

export const config = { path: "/api/communities" };

export default async function handler() {
  try {
    const countries = {};
    for (const submission of await listSubmissions()) {
      if (!isApproved(submission)) continue;
      const entry = toCommunity(submission);
      if (!entry) continue;
      (countries[entry.country] ??= []).push(entry.community);
    }
    return Response.json(
      { countries },
      {
        headers: {
          // Netlify's CDN keeps the answer for 5 minutes, so the function runs
          // at most about once per 5 minutes however busy the site is.
          "Cache-Control": "public, max-age=0, must-revalidate",
          "Netlify-CDN-Cache-Control": "public, durable, max-age=300, stale-while-revalidate=3600",
        },
      }
    );
  } catch (err) {
    console.error(err);
    return Response.json({ error: "Submissions are not available right now." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
