import { NextRequest, NextResponse } from "next/server";
import { createServiceClient } from "@/lib/supabase/server";
import { generateContractPdf } from "@/lib/pdf-generator";
import { sendSignedContract } from "@/lib/resend";
import type { SigningSession, ContractTemplate } from "@/types/database";

export async function POST(request: NextRequest) {
  try {
    const { session_id } = await request.json();
    if (!session_id) {
      return NextResponse.json(
        { error: "session_id is required" },
        { status: 400 },
      );
    }

    const supabase = await createServiceClient();

    const { data: session, error: sessionError } = await supabase
      .from("signing_sessions")
      .select("*")
      .eq("id", session_id)
      .single();

    if (sessionError || !session) {
      console.error("Session not found:", sessionError);
      return NextResponse.json(
        { error: "Session not found" },
        { status: 404 },
      );
    }

    const typedSession = session as SigningSession;

    if (typedSession.status !== "completed" || !typedSession.signed_at) {
      return NextResponse.json(
        { error: "Session is not completed" },
        { status: 400 },
      );
    }

    // Already generated
    if (typedSession.immutable_pdf_path) {
      return NextResponse.json({ success: true, already_generated: true });
    }

    // Fetch the template version locked at contract review time
    const templateQuery = typedSession.template_version
      ? supabase
          .from("contract_templates")
          .select("*")
          .eq("version", typedSession.template_version)
          .single()
      : supabase
          .from("contract_templates")
          .select("*")
          .eq("is_active", true)
          .single();

    const { data: template, error: templateError } = await templateQuery;
    if (templateError || !template) {
      console.error("Template not found:", templateError);
      return NextResponse.json(
        { error: "Contract template not found" },
        { status: 500 },
      );
    }

    const typedTemplate = template as ContractTemplate;

    const { pdfBytes, sha256 } = await generateContractPdf(
      typedSession,
      typedTemplate.html_content,
    );

    // Upload to Supabase Storage
    const storagePath = `contracts/${session_id}/contract-${session_id}.pdf`;
    const { error: uploadError } = await supabase.storage
      .from("signed-contracts")
      .upload(storagePath, pdfBytes, {
        contentType: "application/pdf",
        upsert: false,
      });

    if (uploadError) {
      console.error("Failed to upload PDF:", uploadError);
      // Continue even if storage fails — the PDF can still be emailed
    }

    // Update session with PDF path and hash
    await supabase
      .from("signing_sessions")
      .update({
        immutable_pdf_path: storagePath,
        audit_chain_hash: sha256,
      })
      .eq("id", session_id);

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      "0.0.0.0";
    const userAgent = request.headers.get("user-agent") || "";

    await supabase.from("audit_trail").insert({
      session_id,
      event_type: "pdf_generated",
      ip_address: ip,
      user_agent: userAgent,
      metadata: { sha256, storage_path: storagePath },
    });

    // Send contract email
    const emailResult = await sendSignedContract(
      typedSession.email,
      typedSession.legal_name,
      session_id,
      pdfBytes,
    );

    if (emailResult.success) {
      await supabase.from("audit_trail").insert({
        session_id,
        event_type: "email_delivered",
        ip_address: ip,
        user_agent: userAgent,
        metadata: { email: typedSession.email },
      });
    }

    return NextResponse.json({ success: true, sha256 });
  } catch (err) {
    console.error("Generate PDF error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
