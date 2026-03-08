import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { createClient } from "@/lib/supabase/server";
import { MAX_VERIFICATION_ATTEMPTS } from "@/lib/signing";

function hashCode(code: string): string {
  return crypto.createHash("sha256").update(code).digest("hex");
}

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { session_id, code } = await request.json();
    if (!session_id || !code) {
      return NextResponse.json(
        { error: "session_id and code are required" },
        { status: 400 },
      );
    }

    const { data: session, error: fetchError } = await supabase
      .from("signing_sessions")
      .select(
        "id, user_id, verification_code_hash, verification_expires_at, verification_attempts, status",
      )
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

    if (session.verification_attempts >= MAX_VERIFICATION_ATTEMPTS) {
      return NextResponse.json(
        { error: "Maximum verification attempts exceeded" },
        { status: 429 },
      );
    }

    if (
      !session.verification_code_hash ||
      !session.verification_expires_at
    ) {
      return NextResponse.json(
        { error: "No verification code has been sent" },
        { status: 400 },
      );
    }

    if (new Date(session.verification_expires_at) < new Date()) {
      return NextResponse.json(
        { error: "Verification code has expired. Please request a new one." },
        { status: 400 },
      );
    }

    // Increment attempts regardless of success
    await supabase
      .from("signing_sessions")
      .update({
        verification_attempts: session.verification_attempts + 1,
      })
      .eq("id", session_id);

    const providedHash = hashCode(code.toString().trim());
    if (providedHash !== session.verification_code_hash) {
      const remaining =
        MAX_VERIFICATION_ATTEMPTS - (session.verification_attempts + 1);
      return NextResponse.json(
        {
          error:
            remaining > 0
              ? `Invalid code. ${remaining} attempt${remaining === 1 ? "" : "s"} remaining.`
              : "Maximum verification attempts exceeded.",
          attempts_remaining: remaining,
        },
        { status: 400 },
      );
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      "0.0.0.0";
    const userAgent = request.headers.get("user-agent") || "";

    await supabase
      .from("signing_sessions")
      .update({
        email_verified_at: new Date().toISOString(),
        status: "pending_signature",
        verification_code_hash: null,
      })
      .eq("id", session_id);

    await supabase.from("audit_trail").insert({
      session_id,
      event_type: "email_verified",
      ip_address: ip,
      user_agent: userAgent,
      metadata: { verified: true },
    });

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Verify code error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
