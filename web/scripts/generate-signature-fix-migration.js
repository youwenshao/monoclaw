#!/usr/bin/env node
/**
 * Generates supabase/migrations/009_fix_director_signature_image.sql
 * to replace the placeholder director signature in contract_templates with
 * the image at web/src/content/legal/director-signature.jpg.
 *
 * Run from repo root: node web/scripts/generate-signature-fix-migration.js
 */

const { readFile, writeFile } = require("fs/promises");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.resolve(__dirname, "..");
const DIRECTOR_SIGNATURE_PATH = path.join(
  WEB_ROOT,
  "src",
  "content",
  "legal",
  "director-signature.jpg"
);
const MIGRATION_PATH = path.join(
  REPO_ROOT,
  "supabase",
  "migrations",
  "009_fix_director_signature_image.sql"
);

async function main() {
  const buf = await readFile(DIRECTOR_SIGNATURE_PATH);
  const base64 = buf.toString("base64");

  // Replace any existing data:image/jpeg;base64,XXXX with the correct image.
  // Use regex_replace so we match whatever placeholder is currently in the DB.
  const sql = `-- Replace placeholder director signature in contract template v1.0
-- with the image at web/src/content/legal/director-signature.jpg.

UPDATE contract_templates
SET html_content = regex_replace(
  html_content,
  'src="data:image/jpeg;base64,[^"]+"',
  'src="data:image/jpeg;base64,${base64}"'
)
WHERE version = 'v1.0'
  AND html_content ~ 'src="data:image/jpeg;base64,';
`;

  await writeFile(MIGRATION_PATH, sql, "utf-8");
  console.log("Wrote", MIGRATION_PATH);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
