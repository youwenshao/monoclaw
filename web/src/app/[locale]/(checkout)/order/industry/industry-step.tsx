"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { INDUSTRY_VERTICALS, CLIENT_PERSONAS } from "@/lib/constants";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowRight, ArrowLeft, Building2, Briefcase, UtensilsCrossed, Calculator, Scale, Stethoscope, HardHat, Ship, GraduationCap, Code, Store, BookOpen } from "lucide-react";

const icons: Record<string, React.ReactNode> = {
  "real-estate": <Building2 className="h-5 w-5" />,
  "immigration": <Briefcase className="h-5 w-5" />,
  "fnb-hospitality": <UtensilsCrossed className="h-5 w-5" />,
  "accounting": <Calculator className="h-5 w-5" />,
  "legal": <Scale className="h-5 w-5" />,
  "medical-dental": <Stethoscope className="h-5 w-5" />,
  "construction": <HardHat className="h-5 w-5" />,
  "import-export": <Ship className="h-5 w-5" />,
  "academic-researcher": <GraduationCap className="h-5 w-5" />,
  "vibe-coder": <Code className="h-5 w-5" />,
  "solopreneur": <Store className="h-5 w-5" />,
  "curious-student": <BookOpen className="h-5 w-5" />,
};

export function IndustryStep() {
  const t = useTranslations("order");
  const { order, setIndustry, setPersonas, setCurrentStep } = useCheckout();
  const router = useRouter();

  function handleBack() {
    setCurrentStep(2);
    router.push("/order/addons" as never);
  }

  function handleNext() {
    setCurrentStep(4);
    router.push("/order/review" as never);
  }

  function togglePersona(slug: string) {
    const current = [...order.personas];
    const idx = current.indexOf(slug);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(slug);
    setPersonas(current);
  }

  return (
    <>
      <CheckoutSteps currentStep={3} />
      <h1 className="mb-2 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-8 text-muted-foreground">{t("step3")}</p>

      <div className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">Select Your Industry</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {INDUSTRY_VERTICALS.map((ind) => (
            <Card
              key={ind.slug}
              className={`cursor-pointer transition-all ${
                order.industry === ind.slug
                  ? "border-primary ring-2 ring-primary/20"
                  : "hover:border-primary/50"
              }`}
              onClick={() => setIndustry(ind.slug)}
            >
              <CardHeader className="p-4">
                <div className="mb-2 flex items-center gap-2">
                  <div className="rounded-md bg-primary/10 p-1.5 text-primary">
                    {icons[ind.slug]}
                  </div>
                </div>
                <CardTitle className="text-sm">{ind.name}</CardTitle>
                <CardDescription className="line-clamp-2 text-xs">
                  {ind.softwareStack.length} pre-loaded tools
                </CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>

      <div className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">Additional Profiles <span className="text-sm font-normal text-muted-foreground">(optional, multi-select)</span></h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CLIENT_PERSONAS.map((p) => (
            <label
              key={p.slug}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                order.personas.includes(p.slug) ? "border-primary bg-primary/5" : "hover:bg-muted/50"
              }`}
            >
              <Checkbox
                checked={order.personas.includes(p.slug)}
                onCheckedChange={() => togglePersona(p.slug)}
                className="mt-0.5"
              />
              <div>
                <div className="flex items-center gap-2">
                  {icons[p.slug]}
                  <span className="text-sm font-medium">{p.name}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{p.tagline}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Button size="lg" onClick={handleNext} disabled={!order.industry}>
          Continue <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </>
  );
}
