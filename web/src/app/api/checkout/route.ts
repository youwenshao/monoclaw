import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { createClient } from "@/lib/supabase/server";
import { SOFTWARE_BASE_PRICE_HKD, MODEL_CATEGORIES, LLM_MODELS, BUNDLES } from "@/lib/constants";

/** Configuration fee: 40% deposit at checkout, 60% due 7 days after receipt of hardware. */
const DEPOSIT_RATIO = 0.4;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { hardwareType, hardwareConfig, addons, signingSessionId } = body;

    // Get authenticated user for client_reference_id
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    const lineItems: { price_data: { currency: string; product_data: { name: string; description?: string }; unit_amount: number }; quantity: number }[] = [
      {
        price_data: {
          currency: "hkd",
          product_data: {
            name: "OpenClaw Software Suite (40% deposit)",
            description: `All 12 tool suites included | Hardware: ${hardwareType} | Balance (60%) due 7 days after delivery`,
          },
          unit_amount: Math.round(SOFTWARE_BASE_PRICE_HKD * 100 * DEPOSIT_RATIO),
        },
        quantity: 1,
      },
    ];

    if (addons.bundle) {
      const bundle = BUNDLES.find((b) => b.id === addons.bundle);
      if (bundle) {
        lineItems.push({
          price_data: {
            currency: "hkd",
            product_data: {
              name: `${bundle.name} (40% deposit)`,
              description: bundle.description,
            },
            unit_amount: Math.round(bundle.priceHkd * 100 * DEPOSIT_RATIO),
          },
          quantity: 1,
        });
      }
    } else if (addons.models && addons.models.length > 0) {
      for (const modelId of addons.models) {
        const model = LLM_MODELS.find((m) => m.id === modelId);
        if (!model) continue;
        const category = MODEL_CATEGORIES.find((c) => c.id === model.category);
        if (!category) continue;
        lineItems.push({
          price_data: {
            currency: "hkd",
            product_data: {
              name: `${model.name} ${model.parameterSize} (40% deposit)`,
              description: `${category.name} model - ${model.description}`,
            },
            unit_amount: Math.round(category.priceHkd * 100 * DEPOSIT_RATIO),
          },
          quantity: 1,
        });
      }
    }

    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

    const session = await getStripe().checkout.sessions.create({
      payment_method_types: ["card"],
      line_items: lineItems,
      mode: "payment",
      success_url: `${appUrl}/en/order/confirmation/{CHECKOUT_SESSION_ID}`,
      cancel_url: `${appUrl}/en/order/review`,
      client_reference_id: user?.id || undefined,
      metadata: {
        hardwareType,
        hardwareConfig: JSON.stringify(hardwareConfig),
        addons: JSON.stringify(addons),
        signingSessionId: signingSessionId || "",
      },
    });

    return NextResponse.json({ url: session.url });
  } catch (error) {
    console.error("Checkout error:", error);
    return NextResponse.json(
      { error: "Failed to create checkout session" },
      { status: 500 }
    );
  }
}
