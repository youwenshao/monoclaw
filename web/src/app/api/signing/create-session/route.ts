import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { validateIdentityForm, type IdentityFormData } from "@/lib/signing";

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body: IdentityFormData = await request.json();
    const errors = validateIdentityForm(body);

    if (errors.length > 0) {
      return NextResponse.json({ error: errors[0], errors }, { status: 400 });
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      request.headers.get("x-real-ip") ||
      "0.0.0.0";
    const userAgent = request.headers.get("user-agent") || "";

    const { data: session, error } = await supabase
      .from("signing_sessions")
      .insert({
        user_id: user.id,
        client_type: body.clientType,
        legal_name: body.legalName.trim(),
        entity_jurisdiction: body.entityJurisdiction || null,
        br_number: body.brNumber?.replace(/[\s-]/g, "") || null,
        representative_name: body.representativeName?.trim() || null,
        representative_title: body.representativeTitle?.trim() || null,
        email: body.email.trim().toLowerCase(),
        ip_address: ip,
        user_agent: userAgent,
      })
      .select("id")
      .single();

    if (error) {
      console.error("Failed to create signing session:", error);
      return NextResponse.json(
        { error: "Failed to create session" },
        { status: 500 },
      );
    }

    return NextResponse.json({ session_id: session.id });
  } catch (err) {
    console.error("Create session error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}
