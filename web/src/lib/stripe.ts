import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  typescript: true,
});

export const STRIPE_PRICES = {
  softwareSuite: "price_openclaw_suite",
  models: {
    fast: "price_model_fast",
    standard: "price_model_standard",
    think: "price_model_think",
    coder: "price_model_coder",
  },
  bundles: {
    pro: "price_bundle_pro",
    max: "price_bundle_max",
  },
} as const;

export function formatHKD(amount: number): string {
  return new Intl.NumberFormat("en-HK", {
    style: "currency",
    currency: "HKD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}
