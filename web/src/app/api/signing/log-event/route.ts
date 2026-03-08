import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { AuditEventType } from "@/types/database";

const ALLOWED_CLIENT_EVENTS: AuditEventType[] = [
  "contract_viewed",
  "checkbox_toggled",
];

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { session_id, event_type, metadata } = await request.json();

    if (!session_id || !event_type) {
      return NextResponse.json(
        { error: "session_id and event_type are required" },
        { status: 400 },
      );
    }

    if (!ALLOWED_CLIENT_EVENTS.includes(event_type)) {
      return NextResponse.json(
        { error: "Invalid event type" },
        { status: 400 },
      );
    }

    const { data: session } = await supabase
      .from("signing_sessions")
      .select("id, user_id, status")
      .eq("id", session_id)
      .single();

    if (!session || session.user_id !== user.id) {
      return NextResponse.json(
        { error: "Session not found" },
        { status: 404 },
      );
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      "0.0.0.0";
    const userAgent = request.headers.get("user-agent") || "";

    const { error } = await supabase.from("audit_trail").insert({
      session_id,
      event_type,
      ip_address: ip,
      user_agent: userAgent,
      metadata: metadata || null,
    });

    if (error) {
      console.error("Failed to log audit event:", error);
      return NextResponse.json(
        { error: "Failed to log event" },
        { status: 500 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("Log event error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
