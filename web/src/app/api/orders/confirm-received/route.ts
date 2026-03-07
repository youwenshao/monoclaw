import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { order_id } = body;

  if (!order_id) {
    return NextResponse.json(
      { error: "order_id is required" },
      { status: 400 },
    );
  }

  const { data: order, error: fetchError } = await supabase
    .from("orders")
    .select("id, client_id, status")
    .eq("id", order_id)
    .maybeSingle();

  if (fetchError || !order) {
    return NextResponse.json({ error: "Order not found" }, { status: 404 });
  }

  if (order.client_id !== user.id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  if (order.status !== "shipped") {
    return NextResponse.json(
      { error: "Order is not in shipped status" },
      { status: 409 },
    );
  }

  const { error: updateError } = await supabase
    .from("orders")
    .update({ status: "delivered" })
    .eq("id", order_id);

  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 });
  }

  await supabase.from("order_status_history").insert({
    order_id,
    from_status: "shipped",
    to_status: "delivered",
    updated_by: user.id,
    notes: "Device reception confirmed by client",
  });

  return NextResponse.json({ success: true });
}
