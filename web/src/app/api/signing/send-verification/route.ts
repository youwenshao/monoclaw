import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { createClient } from "@/lib/supabase/server";
import { sendVerificationCode } from "@/lib/resend";
import {
  VERIFICATION_CODE_LENGTH,
  VERIFICATION_EXPIRY_MINUTES,
  MAX_VERIFICATION_ATTEMPTS,
} from "@/lib/signing";

function generateCode(): string {
  const max = Math.pow(10, VERIFICATION_CODE_LENGTH);
  const min = Math.pow(10, VERIFICATION_CODE_LENGTH - 1);
  return String(crypto.randomInt(min, max));
}

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

    const { session_id } = await request.json();
    if (!session_id) {
      return NextResponse.json(
        { error: "session_id is required" },
        { status: 400 },
      );
    }

    const { data: session, error: fetchError } = await supabase
      .from("signing_sessions")
      .select("id, email, verification_attempts, status, user_id")
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
        {
          error:
            "Maximum verification attempts reached. Please create a new session.",
        },
        { status: 429 },
      );
    }

    const code = generateCode();
    const expiresAt = new Date(
      Date.now() + VERIFICATION_EXPIRY_MINUTES * 60 * 1000,
    ).toISOString();

    const { error: updateError } = await supabase
      .from("signing_sessions")
      .update({
        verification_code_hash: hashCode(code),
        verification_expires_at: expiresAt,
      })
      .eq("id", session_id);

    if (updateError) {
      console.error("Failed to store verification code:", updateError);
      return NextResponse.json(
        { error: "Failed to prepare verification" },
        { status: 500 },
      );
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      "0.0.0.0";
    const userAgent = request.headers.get("user-agent") || "";

    await supabase.from("audit_trail").insert({
      session_id,
      event_type: "email_sent",
      ip_address: ip,
      user_agent: userAgent,
      metadata: { email: session.email },
    });

    const result = await sendVerificationCode(session.email, code);
    if (!result.success) {
      return NextResponse.json(
        { error: result.error || "Failed to send email" },
        { status: 500 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Send verification error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
