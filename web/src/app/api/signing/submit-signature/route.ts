import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSignatureName, AGREEMENT_CHECKBOXES } from "@/lib/signing";

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { session_id, signature_font_text, agreement_checks } =
      await request.json();

    if (!session_id || !signature_font_text || !agreement_checks) {
      return NextResponse.json(
        { error: "Missing required fields" },
        { status: 400 },
      );
    }

    if (
      !Array.isArray(agreement_checks) ||
      agreement_checks.length !== AGREEMENT_CHECKBOXES.length ||
      !agreement_checks.every((c: unknown) => c === true)
    ) {
      return NextResponse.json(
        { error: "All agreement checkboxes must be checked" },
        { status: 400 },
      );
    }

    const { data: session, error: fetchError } = await supabase
      .from("signing_sessions")
      .select("*")
      .eq("id", session_id)
      .single();

    if (fetchError || !session) {
      return NextResponse.json(
        { error: "Session not found" },
        { status: 404 },
      );
    }

    if (session.user_id !== user.id) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }

    if (session.status !== "pending_signature") {
      return NextResponse.json(
        { error: "Session is not ready for signature" },
        { status: 400 },
      );
    }

    if (!session.email_verified_at) {
      return NextResponse.json(
        { error: "Email must be verified before signing" },
        { status: 400 },
      );
    }

    const expectedName = getSignatureName(session);
    if (signature_font_text.trim() !== expectedName) {
      return NextResponse.json(
        {
          error: `Signature must exactly match: ${expectedName}`,
        },
        { status: 400 },
      );
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      "0.0.0.0";
    const userAgent = request.headers.get("user-agent") || "";

    const { error: updateError } = await supabase
      .from("signing_sessions")
      .update({
        signature_font_text: signature_font_text.trim(),
        agreement_checks,
        signed_at: new Date().toISOString(),
        status: "completed",
      })
      .eq("id", session_id);

    if (updateError) {
      console.error("Failed to update signing session:", updateError);
      return NextResponse.json(
        { error: "Failed to submit signature" },
        { status: 500 },
      );
    }

    await supabase.from("audit_trail").insert({
      session_id,
      event_type: "signature_submitted",
      ip_address: ip,
      user_agent: userAgent,
      metadata: {
        signature_font_text: signature_font_text.trim(),
        agreement_checks,
      },
    });

    // Trigger async PDF generation via internal call
    const baseUrl =
      process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
    fetch(`${baseUrl}/api/signing/generate-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id, _internal: true }),
    }).catch((err) => {
      console.error("Failed to trigger PDF generation:", err);
    });

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Submit signature error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
