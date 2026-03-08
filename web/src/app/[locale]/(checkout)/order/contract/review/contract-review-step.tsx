"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { createClient } from "@/lib/supabase/client";
import { AGREEMENT_CHECKBOXES, MIN_REVIEW_SECONDS } from "@/lib/signing";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, ArrowRight, FileText, Loader2 } from "lucide-react";
import type { SigningSession, ContractTemplate } from "@/types/database";

function renderContractHtml(
  template: string,
  session: SigningSession,
): string {
  let html = template;

  if (session.client_type === "individual") {
    html = html.replace(
      /\{\{#if_individual\}\}([\s\S]*?)\{\{\/if_individual\}\}/g,
      "$1",
    );
    html = html.replace(
      /\{\{#if_entity\}\}[\s\S]*?\{\{\/if_entity\}\}/g,
      "",
    );
  } else {
    html = html.replace(
      /\{\{#if_entity\}\}([\s\S]*?)\{\{\/if_entity\}\}/g,
      "$1",
    );
    html = html.replace(
      /\{\{#if_individual\}\}[\s\S]*?\{\{\/if_individual\}\}/g,
      "",
    );
  }

  html = html.replace(/\{\{legal_name\}\}/g, session.legal_name);
  html = html.replace(
    /\{\{entity_jurisdiction\}\}/g,
    session.entity_jurisdiction || "",
  );
  html = html.replace(/\{\{br_number\}\}/g, session.br_number || "");
  html = html.replace(
    /\{\{representative_name\}\}/g,
    session.representative_name || "",
  );
  html = html.replace(
    /\{\{representative_title\}\}/g,
    session.representative_title || "",
  );
  html = html.replace(
    /\{\{signed_date\}\}/g,
    new Date().toLocaleDateString("en-HK", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }),
  );
  html = html.replace(/\{\{contract_id\}\}/g, session.id);

  return html;
}

export function ContractReviewStep() {
  const router = useRouter();
  const { order } = useCheckout();
  const sessionId = order.signingSessionId;

  const [session, setSession] = useState<SigningSession | null>(null);
  const [template, setTemplate] = useState<ContractTemplate | null>(null);
  const [checks, setChecks] = useState<boolean[]>(
    Array(AGREEMENT_CHECKBOXES.length).fill(false),
  );
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [loading, setLoading] = useState(true);

  const allChecked = checks.every(Boolean);
  const timerComplete = timerSeconds >= MIN_REVIEW_SECONDS;
  const canProceed = allChecked && timerComplete;

  useEffect(() => {
    if (!sessionId) {
      router.push("/order/contract" as never);
      return;
    }

    async function load() {
      const supabase = createClient();

      const [sessionRes, templateRes] = await Promise.all([
        supabase
          .from("signing_sessions")
          .select("*")
          .eq("id", sessionId!)
          .single(),
        supabase
          .from("contract_templates")
          .select("*")
          .eq("is_active", true)
          .single(),
      ]);

      if (sessionRes.data) setSession(sessionRes.data as SigningSession);
      if (templateRes.data) setTemplate(templateRes.data as ContractTemplate);
      setLoading(false);

      // Lock template version on the session
      if (sessionRes.data && templateRes.data) {
        await supabase
          .from("signing_sessions")
          .update({ template_version: (templateRes.data as ContractTemplate).version })
          .eq("id", sessionId!);

        // Log contract viewed
        await fetch("/api/signing/log-event", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            event_type: "contract_viewed",
            metadata: {
              template_version: (templateRes.data as ContractTemplate).version,
            },
          }),
        });
      }
    }

    load();
  }, [sessionId, router]);

  // Review timer
  useEffect(() => {
    if (loading) return;
    const interval = setInterval(() => {
      setTimerSeconds((s) => {
        if (s >= MIN_REVIEW_SECONDS) {
          clearInterval(interval);
          return s;
        }
        return s + 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [loading]);

  const handleCheckChange = useCallback(
    (index: number, checked: boolean) => {
      const newChecks = [...checks];
      newChecks[index] = checked;
      setChecks(newChecks);

      // Log to audit trail
      fetch("/api/signing/log-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          event_type: "checkbox_toggled",
          metadata: {
            checkbox_index: index,
            checkbox_text: AGREEMENT_CHECKBOXES[index],
            checked,
          },
        }),
      }).catch(() => {});
    },
    [checks, sessionId],
  );

  function handleBack() {
    router.push("/order/contract/verify" as never);
  }

  function handleContinue() {
    if (!canProceed) return;
    router.push("/order/contract/sign" as never);
  }

  if (loading) {
    return (
      <>
        <CheckoutSteps currentStep={5} />
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </>
    );
  }

  if (!session || !template) {
    return (
      <>
        <CheckoutSteps currentStep={5} />
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-muted-foreground">
              Unable to load contract. Please go back and try again.
            </p>
          </CardContent>
        </Card>
      </>
    );
  }

  const contractHtml = renderContractHtml(template.html_content, session);

  return (
    <>
      <CheckoutSteps currentStep={5} />
      <h1 className="mb-2 text-3xl font-bold">Review Contract</h1>
      <p className="mb-8 text-muted-foreground">
        Please read the entire agreement carefully before proceeding.
      </p>

      {/* Contract Display */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Service Agreement (v{template.version})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            className="prose prose-sm dark:prose-invert max-h-[500px] overflow-y-auto rounded-md border bg-muted/30 p-6"
            dangerouslySetInnerHTML={{ __html: contractHtml }}
          />
        </CardContent>
      </Card>

      {/* Review Timer */}
      {!timerComplete && (
        <Card className="mb-6 border-amber-500/30 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="pt-6">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-amber-800 dark:text-amber-200">
                Minimum review time
              </span>
              <span className="font-mono text-amber-800 dark:text-amber-200">
                {MIN_REVIEW_SECONDS - timerSeconds}s remaining
              </span>
            </div>
            <Progress
              value={(timerSeconds / MIN_REVIEW_SECONDS) * 100}
              className="h-2"
            />
          </CardContent>
        </Card>
      )}

      {/* Agreement Checkboxes */}
      <Card className="mb-6">
        <CardContent className="space-y-4 pt-6">
          {AGREEMENT_CHECKBOXES.map((text, i) => (
            <label
              key={i}
              className="flex cursor-pointer items-start gap-3"
            >
              <Checkbox
                checked={checks[i]}
                onCheckedChange={(checked) =>
                  handleCheckChange(i, checked === true)
                }
                className="mt-0.5"
              />
              <span className="text-sm leading-relaxed">{text}</span>
            </label>
          ))}
        </CardContent>
      </Card>

      <div className="mt-8 flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Button size="lg" onClick={handleContinue} disabled={!canProceed}>
          <ArrowRight className="mr-2 h-4 w-4" />
          Proceed to Sign
        </Button>
      </div>
    </>
  );
}
