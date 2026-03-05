import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { createServiceClient } from "@/lib/supabase/server";
import { LLM_MODELS, MODEL_CATEGORIES, BUNDLES } from "@/lib/constants";
import type Stripe from "stripe";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const signature = request.headers.get("stripe-signature");

  if (!signature) {
    return NextResponse.json({ error: "No signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = getStripe().webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (err) {
    console.error("Webhook signature verification failed:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    await handleCheckoutCompleted(session);
  }

  return NextResponse.json({ received: true });
}

async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  const supabase = await createServiceClient();
  const metadata = session.metadata || {};

  const addons = metadata.addons ? JSON.parse(metadata.addons) : { models: [], bundle: null };
  const personas = metadata.personas ? JSON.parse(metadata.personas) : [];
  const hardwareConfig = metadata.hardwareConfig ? JSON.parse(metadata.hardwareConfig) : {};

  const { data: order, error: orderError } = await supabase
    .from("orders")
    .insert({
      client_id: session.client_reference_id || "00000000-0000-0000-0000-000000000000",
      status: "paid",
      hardware_type: metadata.hardwareType as "mac_mini_m4" | "imac_m4",
      hardware_config: hardwareConfig,
      total_price_hkd: Math.round((session.amount_total || 0) / 100),
      stripe_payment_intent_id: session.payment_intent as string,
      stripe_checkout_session_id: session.id,
      notes: `Industry: ${metadata.industry}, Personas: ${personas.join(", ")}`,
    })
    .select()
    .single();

  if (orderError) {
    console.error("Failed to create order:", orderError);
    return;
  }

  if (addons.bundle) {
    const bundle = BUNDLES.find((b) => b.id === addons.bundle);
    await supabase.from("order_addons").insert({
      order_id: order.id,
      addon_type: "bundle",
      addon_name: addons.bundle,
      category: addons.bundle as "pro_bundle" | "max_bundle",
      price_hkd: bundle?.priceHkd || 0,
    });
  } else if (addons.models?.length > 0) {
    const addonRows = addons.models.map((modelId: string) => {
      const model = LLM_MODELS.find((m) => m.id === modelId);
      const category = model ? MODEL_CATEGORIES.find((c) => c.id === model.category) : null;
      return {
        order_id: order.id,
        addon_type: "model" as const,
        addon_name: modelId,
        category: (model?.category || "fast") as "fast" | "standard" | "think" | "coder",
        price_hkd: category?.priceHkd || 0,
      };
    });
    await supabase.from("order_addons").insert(addonRows);
  }

  await supabase.from("order_status_history").insert({
    order_id: order.id,
    from_status: "pending_payment",
    to_status: "paid",
    notes: "Payment confirmed via Stripe webhook",
  });
}
