import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();

  if (profile?.role !== "admin" && profile?.role !== "technician") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await request.json();
  const { orderId, fromStatus, toStatus } = body;

  const { error: updateError } = await supabase
    .from("orders")
    .update({ status: toStatus })
    .eq("id", orderId);

  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 });
  }

  await supabase.from("order_status_history").insert({
    order_id: orderId,
    from_status: fromStatus,
    to_status: toStatus,
    updated_by: user.id,
    notes: `Status updated by ${profile.role}`,
  });

  return NextResponse.json({ success: true });
}
