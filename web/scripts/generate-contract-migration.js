#!/usr/bin/env node
/**
 * Generates supabase/migrations/007_contract_template_v1_first_section_and_signature.sql
 * from src/content/legal/Final Contract - MonoClaw.html and director-signature.jpg.
 *
 * Run from repo root: node web/scripts/generate-contract-migration.js
 * Or from web/: node scripts/generate-contract-migration.js
 *
 * After editing the source HTML, run this script again to regenerate the migration.
 */

const { readFile, writeFile } = require("fs/promises");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.resolve(__dirname, "..");
const SOURCE_HTML = path.join(
  WEB_ROOT,
  "src",
  "content",
  "legal",
  "Final Contract - MonoClaw.html"
);
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
  "008_fix_contract_template_v1.sql"
);

function extractBodyInnerHtml(html) {
  const bodyOpen = /<body[^>]*>/i.exec(html);
  const bodyClose = html.indexOf("</body>");
  if (!bodyOpen || bodyClose === -1) return html;
  const start = bodyOpen.index + bodyOpen[0].length;
  return html.slice(start, bodyClose).trim();
}

// PARTIES section: from "(1)" through "(2)" and "[CLIENT FULL NAME/ENTITY NAME]" to "Data Subject\"</b>).</p>"
const PARTIES_SECTION_REGEX = /<p class=MsoNormal style='margin-bottom:4\.0pt;text-align:justify;text-justify:\s*inter-ideograph;line-height:110%'><span style='font-family:"Times New Roman",serif'>\(1\)[\s\S]*?\(2\)[\s\S]*?\[CLIENT FULL NAME\/ENTITY NAME\][\s\S]*?Data Subject<\/span>["\u201C\u201D]?<\/b>\)\.<o:p><\/o:p><\/span><\/p>/;

const PARTIES_SECTION_REPLACEMENT = `{{#if_individual}}
<p class=MsoNormal style='margin-bottom:4.0pt;text-align:justify;text-justify:
inter-ideograph;line-height:110%'><span style='font-family:"Times New Roman",serif'>(1)
<b><span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;
padding:0in'>SENTIMENTO TECHNOLOGIES LIMITED</span></b>, a company incorporated
in Hong Kong with company number <span style='border:none windowtext 1.0pt;
mso-border-alt:none windowtext 0in;padding:0in'>79623564 </span>and registered
office at Unit B, 11/F, 23 Thomson Road, Wan Chai, Hong Kong Special
Administrative Region of the People’s Republic of China<b> </b>(<b>“<span
class=SpellE><span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;
padding:0in'>Sentimento</span></span>”, “<span style='border:none windowtext 1.0pt;
mso-border-alt:none windowtext 0in;padding:0in'>Bailee</span>”, “<span
style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;
padding:0in'>Agent</span>”, “<span style='border:none windowtext 1.0pt;
mso-border-alt:none windowtext 0in;padding:0in'>Data User</span>”<span
class=GramE>);</span></b><o:p></o:p></span></p>
<p class=MsoNormal style='margin-bottom:4.0pt;text-align:justify;text-justify:
inter-ideograph;line-height:110%'><span style='font-family:"Times New Roman",serif'>(2) <span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>{{legal_name}}</span>, an individual holding email address <span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>{{email}}</span> (<b>"<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Client</span>", "<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Bailor</span>", "<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Principal</span>", "<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Data Subject</span>"</b>).<o:p></o:p></span></p>
{{/if_individual}}
{{#if_entity}}
<p class=MsoNormal style='margin-bottom:4.0pt;text-align:justify;text-justify:
inter-ideograph;line-height:110%'><span style='font-family:"Times New Roman",serif'>(1)
<b><span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;
padding:0in'>SENTIMENTO TECHNOLOGIES LIMITED</span></b>, a company incorporated
in Hong Kong with company number <span style='border:none windowtext 1.0pt;
mso-border-alt:none windowtext 0in;padding:0in'>79623564 </span>and registered
office at Unit B, 11/F, 23 Thomson Road, Wan Chai, Hong Kong Special
Administrative Region of the People’s Republic of China<b> </b>(<b>“<span
class=SpellE><span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;
padding:0in'>Sentimento</span></span>”, “<span style='border:none windowtext 1.0pt;
mso-border-alt:none windowtext 0in;padding:0in'>Bailee</span>”, “<span
style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;
padding:0in'>Agent</span>”, “<span style='border:none windowtext 1.0pt;
mso-border-alt:none windowtext 0in;padding:0in'>Data User</span>”<span
class=GramE>);</span></b><o:p></o:p></span></p>
<p class=MsoNormal style='margin-bottom:4.0pt;text-align:justify;text-justify:
inter-ideograph;line-height:110%'><span style='font-family:"Times New Roman",serif'>(2) <span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>{{legal_name}}</span>, incorporated in <span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>{{entity_jurisdiction}}</span> with company number <span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>{{br_number}}</span> (<b>"<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Client</span>", "<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Bailor</span>", "<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Principal</span>", "<span style='border:none windowtext 1.0pt;mso-border-alt:none windowtext 0in;padding:0in'>Data Subject</span>"</b>).<o:p></o:p></span></p>
{{/if_entity}}`;

// Regex to find and remove the missing asset placeholder (v:shapetype, v:shape, and img tags)
const MISSING_ASSET_REGEX = /<span style='font-family:\s*"Times New Roman",serif;mso-fareast-font-family:"Times New Roman";mso-font-kerning:\s*0pt;mso-no-proof:yes'><!--\[if gte vml 1\]>[\s\S]*?<!\[endif\]-->\s*<!\[if !vml\]><img[\s\S]*?src="Final%20Contract%20-%20MonoClaw\.fld\/image001\.jpg"[\s\S]*?><!\[endif\]><\/span>/;

// Signature line: after "Signature:</span></b>" there's a span with " <o:p></o:p></span>". Replace that space+o:p with the conditional signature.
const SIGNATURE_BLANK_REGEX = /(Signature:<\/span><\/b><span style='font-family:"Times New Roman",serif;[\s\S]*?mso-ligatures:\s*none'>) <o:p><\/o:p><\/span>/;

const SIGNATURE_REPLACEMENT = `$1{{#if_individual}}<span class="signature-font">{{legal_name}}</span>{{/if_individual}}{{#if_entity}}<span class="signature-font">{{representative_name}}</span>{{/if_entity}}<o:p></o:p></span>`;

// Blank paragraph between Signature and Date (client block) - replace with conditional Title line for entity
const BLANK_BETWEEN_SIG_AND_DATE_REGEX = /(<p class=MsoNormal style='text-align:justify;text-justify:inter-ideograph;\s*line-height:16\.5pt;tab-stops:49\.6pt'><b><span style='font-family:"Times New Roman",serif;\s*mso-fareast-font-family:"Times New Roman";mso-font-kerning:0pt;mso-ligatures:\s*none'><o:p>&nbsp;<\/o:p><\/span><\/b><\/p>\s*)(<p class=MsoNormal style='text-align:justify;text-justify:inter-ideograph;\s*line-height:16\.5pt;tab-stops:49\.6pt'><b><span style='font-family:"Times New Roman",serif;\s*mso-fareast-font-family:"Times New Roman";mso-font-kerning:0pt;mso-ligatures:\s*none'>Date:)/;

const TITLE_AND_DATE = `{{#if_entity}}
<p class=MsoNormal style='text-align:justify;text-justify:inter-ideograph;
line-height:16.5pt;tab-stops:49.6pt'><b><span style='font-family:"Times New Roman",serif;
mso-fareast-font-family:"Times New Roman";mso-font-kerning:0pt;mso-ligatures:
none'>Title:</span></b><span style='font-family:"Times New Roman",serif;
mso-fareast-font-family:"Times New Roman";mso-font-kerning:0pt;mso-ligatures:
none'> {{representative_title}}<o:p></o:p></span></p>
{{/if_entity}}
$2`;

// Contract ID paragraph to insert before the final </div>
const CONTRACT_ID_PARAGRAPH = `
<p class=MsoNormal style='text-align:justify;text-justify:inter-ideograph;
line-height:16.5pt;tab-stops:49.6pt'><b><span style='font-family:"Times New Roman",serif;
mso-fareast-font-family:"Times New Roman";mso-font-kerning:0pt;mso-ligatures:
none'>Contract ID: </span></b><span style='font-family:"Times New Roman",serif;
mso-fareast-font-family:"Times New Roman";mso-font-kerning:0pt;mso-ligatures:
none'>{{contract_id}}<o:p></o:p></span></p>
`;

async function main() {
  const raw = await readFile(SOURCE_HTML, "utf-8");
  let body = extractBodyInnerHtml(raw);

  // 1. All [DATE] -> {{signed_date}}
  body = body.replace(/\[DATE\]/g, "{{signed_date}}");

  // 2. PARTIES section -> conditional individual/entity blocks
  body = body.replace(PARTIES_SECTION_REGEX, PARTIES_SECTION_REPLACEMENT);
  if (!body.includes("{{#if_individual}}")) {
    throw new Error("Could not find PARTIES section to replace");
  }

  // 3. [CLIENT FULL LEGAL NAME/ENTITY NAME] (in CLIENT block) -> {{legal_name}}
  body = body.replace(/\[CLIENT FULL LEGAL NAME\/ENTITY NAME\]/g, "{{legal_name}}");

  // 4. Signature blank -> conditional signature block
  body = body.replace(SIGNATURE_BLANK_REGEX, SIGNATURE_REPLACEMENT);

  // 5. Blank paragraph between Signature and Date -> conditional Title + Date line
  body = body.replace(BLANK_BETWEEN_SIG_AND_DATE_REGEX, TITLE_AND_DATE);

  // 6. Director signature image: remove missing asset placeholder and insert new signature
  body = body.replace(MISSING_ASSET_REGEX, "");

  const directorSignatureBuffer = await readFile(DIRECTOR_SIGNATURE_PATH);
  const directorSignatureBase64 = directorSignatureBuffer.toString("base64");
  const directorImgParagraph = `
<p class=MsoNormal style='text-align:justify;text-justify:inter-ideograph;
line-height:16.5pt;tab-stops:49.6pt'><img src="data:image/jpeg;base64,${directorSignatureBase64}" alt="Director signature" style="max-height:60pt;display:block;" /></p>
`;
  const directorInsertPoint = body.indexOf("> Director<o:p></o:p></span></p>");
  if (directorInsertPoint !== -1) {
    const after = directorInsertPoint + "> Director<o:p></o:p></span></p>".length;
    body = body.slice(0, after) + directorImgParagraph + body.slice(after);
  }

  // 7. Contract ID before final </div> (insert before last </div> in body)
  const lastDivClose = body.lastIndexOf("</div>");
  if (lastDivClose !== -1) {
    body =
      body.slice(0, lastDivClose) +
      CONTRACT_ID_PARAGRAPH +
      body.slice(lastDivClose);
  }

  const sql = `-- Update contract template v1.0: fix parties section, add director signature.
-- Generated by web/scripts/generate-contract-migration.js
-- Do not edit this file by hand; regenerate after changing the source HTML.

UPDATE contract_templates
SET html_content = $body$
${body}
$body$
WHERE version = 'v1.0';
`;

  await writeFile(MIGRATION_PATH, sql, "utf-8");
  console.log("Wrote", MIGRATION_PATH);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
