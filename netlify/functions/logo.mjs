// GET /api/logo?id=<submission id>: the logo sent with an approved
// submission. Netlify's links to uploaded files expire, so the image is
// fetched here and cached by the CDN for a long time instead.
import { getSubmission, isApproved, fileUrl } from "../lib/submissions.mjs";

export const config = { path: "/api/logo" };

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

export default async function handler(request) {
  const id = new URL(request.url).searchParams.get("id");
  if (!id || !/^[a-f0-9]{24}$/i.test(id)) return new Response("Not found", { status: 404 });
  try {
    const submission = await getSubmission(id);
    const url = isApproved(submission) && fileUrl(submission.data?.logo);
    if (!url) return new Response("Not found", { status: 404, headers: { "Cache-Control": "no-store" } });
    const image = await fetch(url);
    // The storage may not say it's an image; the submission records the type too.
    const type = [image.headers.get("content-type")?.split(";")[0], submission.data.logo?.type].find((t) => IMAGE_TYPES.includes(t));
    if (!image.ok || !IMAGE_TYPES.includes(type)) throw new Error(`Logo ${id}: HTTP ${image.status}, ${type}`);
    return new Response(await image.arrayBuffer(), {
      headers: {
        "Content-Type": type,
        "Cache-Control": "public, max-age=86400",
        "Netlify-CDN-Cache-Control": "public, durable, max-age=2592000",
      },
    });
  } catch (err) {
    console.error(err);
    return new Response("Not available", { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
