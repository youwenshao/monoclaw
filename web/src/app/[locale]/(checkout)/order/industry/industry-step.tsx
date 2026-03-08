"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { TOOL_SUITES } from "@/lib/constants";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  "academic": <GraduationCap className="h-5 w-5" />,
  "vibe-coder": <Code className="h-5 w-5" />,
  "solopreneur": <Store className="h-5 w-5" />,
  "student": <BookOpen className="h-5 w-5" />,
};

export function ToolsShowcaseStep() {
  const t = useTranslations("order");
  const { setCurrentStep } = useCheckout();
  const router = useRouter();

  function handleBack() {
    setCurrentStep(2);
    router.push("/order/addons" as never);
  }

  function handleNext() {
    setCurrentStep(4);
    router.push("/order/review" as never);
  }

  return (
    <>
      <CheckoutSteps currentStep={3} />
      <h1 className="mb-2 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-2 text-muted-foreground">{t("step3")}</p>
      <p className="mb-8 text-muted-foreground">
        Every Mona Mac ships with all 12 tool suites pre-installed. Mona automatically
        routes your requests to the right tool based on context, or you can select one manually.
      </p>

      <div className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">
          12 Tool Suites Included
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TOOL_SUITES.map((suite) => (
            <Card key={suite.id} className="transition-all hover:border-primary/50">
              <CardHeader className="p-4">
                <div className="mb-2 flex items-center gap-2">
                  <div className="rounded-md bg-primary/10 p-1.5 text-primary">
                    {icons[suite.id]}
                  </div>
                  <CardTitle className="text-sm">{suite.name}</CardTitle>
                </div>
                <CardDescription className="line-clamp-2 text-xs">
                  {suite.description}
                </CardDescription>
                <div className="mt-2 flex flex-wrap gap-1">
                  {suite.tools.map((tool) => (
                    <Badge key={tool} variant="outline" className="text-xs">
                      {tool}
                    </Badge>
                  ))}
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Button size="lg" onClick={handleNext}>
          Continue <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </>
  );
}
