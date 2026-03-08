"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { VERIFICATION_CODE_LENGTH } from "@/lib/signing";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ArrowLeft, Loader2, Mail, RotateCcw } from "lucide-react";

export function VerifyStep() {
  const router = useRouter();
  const { order } = useCheckout();
  const sessionId = order.signingSessionId;

  const [digits, setDigits] = useState<string[]>(
    Array(VERIFICATION_CODE_LENGTH).fill(""),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (!sessionId) {
      router.push("/order/contract" as never);
    }
  }, [sessionId, router]);

  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(
        () => setResendCooldown((c) => c - 1),
        1000,
      );
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  const handleDigitChange = useCallback(
    (index: number, value: string) => {
      if (!/^\d*$/.test(value)) return;
      const newDigits = [...digits];
      newDigits[index] = value.slice(-1);
      setDigits(newDigits);
      setError(null);

      if (value && index < VERIFICATION_CODE_LENGTH - 1) {
        inputRefs.current[index + 1]?.focus();
      }
    },
    [digits],
  );

  const handleKeyDown = useCallback(
    (index: number, e: React.KeyboardEvent) => {
      if (e.key === "Backspace" && !digits[index] && index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
    },
    [digits],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      e.preventDefault();
      const pasted = e.clipboardData
        .getData("text")
        .replace(/\D/g, "")
        .slice(0, VERIFICATION_CODE_LENGTH);
      if (!pasted) return;
      const newDigits = [...digits];
      for (let i = 0; i < pasted.length; i++) {
        newDigits[i] = pasted[i];
      }
      setDigits(newDigits);
      const focusIdx = Math.min(pasted.length, VERIFICATION_CODE_LENGTH - 1);
      inputRefs.current[focusIdx]?.focus();
    },
    [digits],
  );

  async function handleVerify() {
    const code = digits.join("");
    if (code.length !== VERIFICATION_CODE_LENGTH) {
      setError("Please enter the full verification code");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/signing/verify-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, code }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Verification failed");
        setDigits(Array(VERIFICATION_CODE_LENGTH).fill(""));
        inputRefs.current[0]?.focus();
        return;
      }

      router.push("/order/contract/review" as never);
    } catch {
      setError("An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (resendCooldown > 0) return;
    setResendCooldown(60);
    setError(null);

    try {
      const res = await fetch("/api/signing/send-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.error || "Failed to resend code");
        setResendCooldown(0);
      }
    } catch {
      setError("Failed to resend code");
      setResendCooldown(0);
    }
  }

  function handleBack() {
    router.push("/order/contract" as never);
  }

  return (
    <>
      <CheckoutSteps currentStep={5} />
      <h1 className="mb-2 text-3xl font-bold">Verify Your Email</h1>
      <p className="mb-8 text-muted-foreground">
        Enter the 6-digit code sent to your email address.
      </p>

      <Card className="mx-auto max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Mail className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>Verification Code</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex justify-center gap-2" onPaste={handlePaste}>
            {digits.map((digit, i) => (
              <Input
                key={i}
                ref={(el) => {
                  inputRefs.current[i] = el;
                }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleDigitChange(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                className="h-14 w-12 text-center text-2xl font-mono"
              />
            ))}
          </div>

          {error && (
            <p className="text-center text-sm text-destructive">{error}</p>
          )}

          <Button
            className="w-full"
            size="lg"
            onClick={handleVerify}
            disabled={
              loading || digits.some((d) => !d)
            }
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Verify
          </Button>

          <div className="text-center">
            <button
              onClick={handleResend}
              disabled={resendCooldown > 0}
              className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
            >
              <RotateCcw className="mr-1 inline h-3 w-3" />
              {resendCooldown > 0
                ? `Resend in ${resendCooldown}s`
                : "Resend code"}
            </button>
          </div>
        </CardContent>
      </Card>

      <div className="mt-8">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
      </div>
    </>
  );
}
