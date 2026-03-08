import { PDFDocument, StandardFonts, rgb, PDFPage, PDFFont } from "pdf-lib";
import crypto from "crypto";
import type { SigningSession } from "@/types/database";

const MARGIN = 50;
const PAGE_WIDTH = 595.28; // A4
const PAGE_HEIGHT = 841.89;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
const FONT_SIZE_BODY = 10;
const FONT_SIZE_H1 = 18;
const FONT_SIZE_H2 = 13;
const FONT_SIZE_SIGNATURE = 16;
const LINE_HEIGHT = 14;

interface RenderContext {
  doc: PDFDocument;
  bodyFont: PDFFont;
  boldFont: PDFFont;
  italicFont: PDFFont;
  y: number;
  page: PDFPage;
  pageNum: number;
}

function addPage(ctx: RenderContext): void {
  ctx.page = ctx.doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
  ctx.y = PAGE_HEIGHT - MARGIN;
  ctx.pageNum++;
}

function ensureSpace(ctx: RenderContext, needed: number): void {
  if (ctx.y - needed < MARGIN) {
    addPage(ctx);
  }
}

function drawText(
  ctx: RenderContext,
  text: string,
  opts: { font?: PDFFont; size?: number; indent?: number } = {},
): void {
  const font = opts.font || ctx.bodyFont;
  const size = opts.size || FONT_SIZE_BODY;
  const indent = opts.indent || 0;

  const words = text.split(/\s+/);
  let line = "";

  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    const width = font.widthOfTextAtSize(test, size);
    if (width > CONTENT_WIDTH - indent && line) {
      ensureSpace(ctx, LINE_HEIGHT);
      ctx.page.drawText(line, {
        x: MARGIN + indent,
        y: ctx.y,
        size,
        font,
        color: rgb(0.1, 0.1, 0.1),
      });
      ctx.y -= LINE_HEIGHT;
      line = word;
    } else {
      line = test;
    }
  }

  if (line) {
    ensureSpace(ctx, LINE_HEIGHT);
    ctx.page.drawText(line, {
      x: MARGIN + indent,
      y: ctx.y,
      size,
      font,
      color: rgb(0.1, 0.1, 0.1),
    });
    ctx.y -= LINE_HEIGHT;
  }
}

function mergeTemplate(
  htmlContent: string,
  session: SigningSession,
): string[] {
  let text = htmlContent;

  // Strip HTML tags and decode entities
  text = text.replace(/<br\s*\/?>/gi, "\n");
  text = text.replace(/<\/p>/gi, "\n\n");
  text = text.replace(/<\/h[12345]>/gi, "\n\n");
  text = text.replace(/<\/div>/gi, "\n");
  text = text.replace(/<[^>]+>/g, "");
  text = text.replace(/&ldquo;/g, "\u201C");
  text = text.replace(/&rdquo;/g, "\u201D");
  text = text.replace(/&rsquo;/g, "\u2019");
  text = text.replace(/&amp;/g, "&");
  text = text.replace(/&middot;/g, "\u00B7");

  // Handle conditionals
  if (session.client_type === "individual") {
    text = text.replace(
      /\{\{#if_individual\}\}([\s\S]*?)\{\{\/if_individual\}\}/g,
      "$1",
    );
    text = text.replace(
      /\{\{#if_entity\}\}[\s\S]*?\{\{\/if_entity\}\}/g,
      "",
    );
  } else {
    text = text.replace(
      /\{\{#if_entity\}\}([\s\S]*?)\{\{\/if_entity\}\}/g,
      "$1",
    );
    text = text.replace(
      /\{\{#if_individual\}\}[\s\S]*?\{\{\/if_individual\}\}/g,
      "",
    );
  }

  // Replace variables
  text = text.replace(/\{\{legal_name\}\}/g, session.legal_name);
  text = text.replace(
    /\{\{entity_jurisdiction\}\}/g,
    session.entity_jurisdiction || "",
  );
  text = text.replace(/\{\{br_number\}\}/g, session.br_number || "");
  text = text.replace(
    /\{\{representative_name\}\}/g,
    session.representative_name || "",
  );
  text = text.replace(
    /\{\{representative_title\}\}/g,
    session.representative_title || "",
  );
  text = text.replace(
    /\{\{signed_date\}\}/g,
    session.signed_at
      ? new Date(session.signed_at).toLocaleDateString("en-HK", {
          year: "numeric",
          month: "long",
          day: "numeric",
        })
      : new Date().toLocaleDateString("en-HK", {
          year: "numeric",
          month: "long",
          day: "numeric",
        }),
  );
  text = text.replace(/\{\{contract_id\}\}/g, session.id);

  // Clean up whitespace
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter((l, i, arr) => !(l === "" && arr[i - 1] === ""));
}

export async function generateContractPdf(
  session: SigningSession,
  templateHtml: string,
): Promise<{ pdfBytes: Uint8Array; sha256: string }> {
  const doc = await PDFDocument.create();
  const bodyFont = await doc.embedFont(StandardFonts.Helvetica);
  const boldFont = await doc.embedFont(StandardFonts.HelveticaBold);
  const italicFont = await doc.embedFont(StandardFonts.HelveticaOblique);

  const firstPage = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);

  const ctx: RenderContext = {
    doc,
    bodyFont,
    boldFont,
    italicFont,
    y: PAGE_HEIGHT - MARGIN,
    page: firstPage,
    pageNum: 1,
  };

  const lines = mergeTemplate(templateHtml, session);

  for (const line of lines) {
    if (line === "") {
      ctx.y -= LINE_HEIGHT * 0.5;
      continue;
    }

    if (line.startsWith("Service Agreement")) {
      ensureSpace(ctx, LINE_HEIGHT * 2);
      drawText(ctx, line, { font: boldFont, size: FONT_SIZE_H1 });
      ctx.y -= LINE_HEIGHT * 0.5;
    } else if (/^\d+\.\s/.test(line)) {
      ctx.y -= LINE_HEIGHT * 0.3;
      ensureSpace(ctx, LINE_HEIGHT * 2);
      drawText(ctx, line, { font: boldFont, size: FONT_SIZE_H2 });
      ctx.y -= LINE_HEIGHT * 0.3;
    } else if (
      line.startsWith("SERVICE PROVIDER:") ||
      line.startsWith("CLIENT:")
    ) {
      ctx.y -= LINE_HEIGHT * 0.3;
      drawText(ctx, line, { font: boldFont, size: FONT_SIZE_BODY });
    } else if (line.startsWith("Signature:")) {
      const sigName =
        session.client_type === "entity"
          ? session.representative_name || session.legal_name
          : session.legal_name;
      drawText(ctx, "Signature:", { font: bodyFont, size: FONT_SIZE_BODY });
      ctx.y -= LINE_HEIGHT * 0.2;
      drawText(ctx, sigName, {
        font: italicFont,
        size: FONT_SIZE_SIGNATURE,
      });
      ctx.y -= LINE_HEIGHT * 0.3;
    } else {
      drawText(ctx, line);
    }
  }

  // Footer with metadata
  ctx.y -= LINE_HEIGHT * 2;
  ensureSpace(ctx, LINE_HEIGHT * 5);
  ctx.page.drawLine({
    start: { x: MARGIN, y: ctx.y },
    end: { x: PAGE_WIDTH - MARGIN, y: ctx.y },
    thickness: 0.5,
    color: rgb(0.7, 0.7, 0.7),
  });
  ctx.y -= LINE_HEIGHT * 1.5;

  const metaLines = [
    `Contract ID: ${session.id}`,
    `Template Version: ${session.template_version || "v1.0"}`,
    `Signed At: ${session.signed_at || new Date().toISOString()}`,
    `IP Address: ${session.ip_address || "N/A"}`,
    `This document was electronically signed via the Native Signing System.`,
  ];

  for (const ml of metaLines) {
    drawText(ctx, ml, { font: bodyFont, size: 8 });
  }

  doc.setTitle("Service Agreement - Sentimento Technologies Limited");
  doc.setAuthor("Sentimento Technologies Limited");
  doc.setSubject(`Contract ${session.id}`);
  doc.setCreator("Native Signing System");
  doc.setCreationDate(new Date());

  const pdfBytes = await doc.save();
  const sha256 = crypto
    .createHash("sha256")
    .update(pdfBytes)
    .digest("hex");

  return { pdfBytes, sha256 };
}
