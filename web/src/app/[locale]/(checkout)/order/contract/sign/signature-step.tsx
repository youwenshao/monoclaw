"use client";

import { useState, useEffect } from "react";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { createClient } from "@/lib/supabase/client";
import { getSignatureName, AGREEMENT_CHECKBOXES } from "@/lib/signing";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Loader2,
  PenLine,
  Check,
} from "lucide-react";
import type { SigningSession } from "@/types/database";

export function SignatureStep() {
  const router = useRouter();
  const { order } = useCheckout();
  const sessionId = order.signingSessionId;

  const [session, setSession] = useState<SigningSession | null>(null);
  const [typedName, setTypedName] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      router.push("/order/contract" as never);
      return;
    }

    const supabase = createClient();
    supabase
      .from("signing_sessions")
      .select("*")
      .eq("id", sessionId)
      .single()
      .then(({ data }) => {
        if (data) setSession(data as SigningSession);
        setLoading(false);
      });
  }, [sessionId, router]);

  const expectedName = session ? getSignatureName(session) : "";
  const nameMatches = typedName.trim() === expectedName;

  async function handleSign() {
    if (!nameMatches || !sessionId) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/signing/submit-signature", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          signature_font_text: typedName.trim(),
          agreement_checks: Array(AGREEMENT_CHECKBOXES.length).fill(true),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to submit signature");
        return;
      }

      setSuccess(true);
      setTimeout(() => {
        router.push("/order/review" as never);
      }, 2000);
    } catch {
      setError("An unexpected error occurred");
    } finally {
      setSubmitting(false);
    }
  }

  function handleBack() {
    router.push("/order/contract/review" as never);
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

  if (!session) {
    return (
      <>
        <CheckoutSteps currentStep={5} />
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-muted-foreground">
              Unable to load session. Please go back and try again.
            </p>
          </CardContent>
        </Card>
      </>
    );
  }

  if (success) {
    return (
      <>
        <CheckoutSteps currentStep={5} />
        <div className="mx-auto max-w-md py-16 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400">
            <Check className="h-8 w-8" />
          </div>
          <h2 className="mb-2 text-2xl font-bold">Contract Signed</h2>
          <p className="text-muted-foreground">
            Your contract has been executed. A copy will be sent to your email.
            Redirecting to payment...
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <CheckoutSteps currentStep={5} />
      <h1 className="mb-2 text-3xl font-bold">Sign Contract</h1>
      <p className="mb-8 text-muted-foreground">
        Review your signature preview and confirm by typing your name exactly
        as shown.
      </p>

      {/* Signature Preview */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PenLine className="h-5 w-5" />
            Signature Preview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Your signature will appear as:
          </p>
          <div className="rounded-lg border-2 border-dashed border-muted-foreground/20 bg-muted/30 p-8 text-center">
            <p
              className="text-4xl text-foreground"
              style={{
                fontFamily: "'Dancing Script', 'Segoe Script', 'Brush Script MT', cursive",
                fontStyle: "italic",
              }}
            >
              {expectedName}
            </p>
          </div>
          {session.client_type === "entity" && (
            <p className="text-xs text-muted-foreground">
              Signing as <strong>{session.representative_title}</strong> of{" "}
              <strong>{session.legal_name}</strong>
            </p>
          )}
        </CardContent>
      </Card>

      {/* Type-to-Confirm */}
      <Card className="mb-6">
        <CardContent className="space-y-4 pt-6">
          <div className="space-y-2">
            <Label htmlFor="confirm-name">
              Type your name exactly as shown above to confirm
            </Label>
            <Input
              id="confirm-name"
              placeholder={expectedName}
              value={typedName}
              onChange={(e) => {
                setTypedName(e.target.value);
                setError(null);
              }}
              className="text-lg"
            />
            {typedName.length > 0 && !nameMatches && (
              <p className="text-xs text-destructive">
                Name must exactly match: {expectedName}
              </p>
            )}
            {nameMatches && (
              <p className="text-xs text-green-600 dark:text-green-400">
                Name confirmed
              </p>
            )}
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 p-3">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="mt-8 flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Button
          size="lg"
          onClick={handleSign}
          disabled={!nameMatches || submitting}
        >
          {submitting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <PenLine className="mr-2 h-4 w-4" />
          )}
          Sign Contract
        </Button>
      </div>
    </>
  );
}
