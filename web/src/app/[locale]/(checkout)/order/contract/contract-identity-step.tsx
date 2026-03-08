"use client";

import { useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import {
  JURISDICTIONS,
  validateIdentityForm,
  type IdentityFormData,
} from "@/lib/signing";
import type { ClientType } from "@/types/database";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  User,
  Loader2,
} from "lucide-react";

export function ContractIdentityStep() {
  const router = useRouter();
  const { setSigningSession, setCurrentStep } = useCheckout();

  const [clientType, setClientType] = useState<ClientType | null>(null);
  const [legalName, setLegalName] = useState("");
  const [email, setEmail] = useState("");
  const [entityJurisdiction, setEntityJurisdiction] = useState("");
  const [brNumber, setBrNumber] = useState("");
  const [representativeName, setRepresentativeName] = useState("");
  const [representativeTitle, setRepresentativeTitle] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  function handleBack() {
    setCurrentStep(4);
    router.push("/order/review" as never);
  }

  async function handleSubmit() {
    if (!clientType) return;

    const formData: IdentityFormData = {
      clientType,
      legalName,
      email,
      entityJurisdiction: clientType === "entity" ? entityJurisdiction : undefined,
      brNumber: clientType === "entity" ? brNumber : undefined,
      representativeName: clientType === "entity" ? representativeName : undefined,
      representativeTitle: clientType === "entity" ? representativeTitle : undefined,
    };

    const validationErrors = validateIdentityForm(formData);
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors([]);
    setLoading(true);

    try {
      const res = await fetch("/api/signing/create-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      const data = await res.json();

      if (!res.ok) {
        setErrors([data.error || "Failed to create session"]);
        return;
      }

      // Trigger verification email
      await fetch("/api/signing/send-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: data.session_id }),
      });

      setSigningSession(data.session_id);
      router.push("/order/contract/verify" as never);
    } catch {
      setErrors(["An unexpected error occurred"]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <CheckoutSteps currentStep={5} />
      <h1 className="mb-2 text-3xl font-bold">Service Agreement</h1>
      <p className="mb-8 text-muted-foreground">
        Identify yourself to proceed with the contract signing process.
      </p>

      {/* Stage 0: Client Type Selection */}
      {!clientType && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card
            className="cursor-pointer transition-colors hover:border-primary"
            onClick={() => setClientType("individual")}
          >
            <CardContent className="flex flex-col items-center gap-3 pt-8 pb-8">
              <User className="h-10 w-10 text-muted-foreground" />
              <CardTitle>Individual Client</CardTitle>
              <p className="text-center text-sm text-muted-foreground">
                Signing in your personal capacity
              </p>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer transition-colors hover:border-primary"
            onClick={() => setClientType("entity")}
          >
            <CardContent className="flex flex-col items-center gap-3 pt-8 pb-8">
              <Building2 className="h-10 w-10 text-muted-foreground" />
              <CardTitle>Corporate Client</CardTitle>
              <p className="text-center text-sm text-muted-foreground">
                Signing on behalf of a company or organization
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Stage 1: Identity Form */}
      {clientType && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {clientType === "individual" ? (
                <User className="h-5 w-5" />
              ) : (
                <Building2 className="h-5 w-5" />
              )}
              {clientType === "individual"
                ? "Individual Client"
                : "Corporate Client"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {clientType === "individual" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="legal-name">
                    Full Legal Name{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="legal-name"
                    placeholder="As appears on your government-issued ID"
                    value={legalName}
                    onChange={(e) => setLegalName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">
                    Email Address{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    We will send a verification code to this address. You must
                    have access to sign.
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="company-name">
                    Company Full Legal Name{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="company-name"
                    placeholder="Exactly as registered"
                    value={legalName}
                    onChange={(e) => setLegalName(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="jurisdiction">
                    Jurisdiction of Incorporation{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={entityJurisdiction}
                    onValueChange={setEntityJurisdiction}
                  >
                    <SelectTrigger id="jurisdiction">
                      <SelectValue placeholder="Select jurisdiction" />
                    </SelectTrigger>
                    <SelectContent>
                      {JURISDICTIONS.map((j) => (
                        <SelectItem key={j} value={j}>
                          {j}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {entityJurisdiction === "Hong Kong" && (
                  <div className="space-y-2">
                    <Label htmlFor="br-number">
                      Business Registration Number
                    </Label>
                    <Input
                      id="br-number"
                      placeholder="8 digits (or 11 for branches)"
                      value={brNumber}
                      onChange={(e) => setBrNumber(e.target.value)}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="rep-name">
                    Representative&apos;s Full Legal Name{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="rep-name"
                    placeholder="Person authorized to sign"
                    value={representativeName}
                    onChange={(e) => setRepresentativeName(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="rep-title">
                    Representative&apos;s Title{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="rep-title"
                    placeholder='e.g., "Director", "Authorized Signatory"'
                    value={representativeTitle}
                    onChange={(e) => setRepresentativeTitle(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="entity-email">
                    Email Address{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="entity-email"
                    type="email"
                    placeholder="Corporate email preferred"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    We will send a verification code to this address. Corporate
                    email preferred for non-repudiation.
                  </p>
                </div>
              </>
            )}

            {errors.length > 0 && (
              <div className="rounded-md bg-destructive/10 p-3">
                {errors.map((err, i) => (
                  <p key={i} className="text-sm text-destructive">
                    {err}
                  </p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="mt-8 flex justify-between">
        <Button
          variant="outline"
          size="lg"
          onClick={clientType ? () => setClientType(null) : handleBack}
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        {clientType && (
          <Button size="lg" onClick={handleSubmit} disabled={loading}>
            {loading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="mr-2 h-4 w-4" />
            )}
            Verify Email
          </Button>
        )}
      </div>
    </>
  );
}
