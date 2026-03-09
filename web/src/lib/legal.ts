import { readFile } from "fs/promises";
import path from "path";

export type LegalSlug =
  | "privacy"
  | "terms"
  | "cookies"
  | "end-user-certificate";

const SLUG_TO_FILENAME: Record<LegalSlug, string> = {
  privacy: "Privacy Policy.html",
  terms: "Terms of Services.html",
  cookies: "Cookie Policy.html",
  "end-user-certificate": "End User Certificate.html",
};

/**
 * Extracts inner HTML of the first <body> element.
 * Word exports use <body ...> with attributes.
 */
function extractBodyInnerHtml(html: string): string {
  const bodyOpen = /<body[^>]*>/i.exec(html);
  const bodyClose = html.indexOf("</body>");
  if (!bodyOpen || bodyClose === -1) return html;
  const start = bodyOpen.index + bodyOpen[0].length;
  return html.slice(start, bodyClose).trim();
}

/**
 * Strips style attributes so Tailwind prose can control typography.
 */
function stripStyleAttributes(html: string): string {
  return html.replace(/\s+style\s*=\s*["'][^"']*["']/gi, "");
}

/**
 * Loads legal HTML from content/legal and returns body inner HTML only.
 * Optionally strips inline styles for consistent prose styling.
 * Call from server only.
 */
export async function getLegalHtml(
  slug: LegalSlug,
  options?: { stripStyles?: boolean },
): Promise<string> {
  const filename = SLUG_TO_FILENAME[slug];
  const filePath = path.join(
    process.cwd(),
    "src",
    "content",
    "legal",
    filename,
  );
  const raw = await readFile(filePath, "utf-8");
  let body = extractBodyInnerHtml(raw);
  if (options?.stripStyles !== false) {
    body = stripStyleAttributes(body);
  }
  return body;
}
