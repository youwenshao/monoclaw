"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";

interface CheckoutStepsProps {
  currentStep: number;
}

export function CheckoutSteps({ currentStep }: CheckoutStepsProps) {
  const t = useTranslations("order");
  const steps = [
    { num: 1, label: t("step1") },
    { num: 2, label: t("step2") },
    { num: 3, label: t("step3") },
    { num: 4, label: t("step4") },
  ];

  return (
    <nav className="mb-10">
      <ol className="flex items-center justify-between">
        {steps.map((step, i) => (
          <li key={step.num} className="flex items-center">
            <div className="flex items-center gap-2">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  step.num < currentStep
                    ? "bg-primary text-primary-foreground"
                    : step.num === currentStep
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {step.num < currentStep ? (
                  <Check className="h-4 w-4" />
                ) : (
                  step.num
                )}
              </div>
              <span
                className={`hidden text-sm sm:inline ${
                  step.num <= currentStep ? "font-medium" : "text-muted-foreground"
                }`}
              >
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`mx-4 h-px w-8 sm:w-16 ${
                  step.num < currentStep ? "bg-primary" : "bg-muted"
                }`}
              />
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
