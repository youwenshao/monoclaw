import type { ClientType } from "@/types/database";

export const JURISDICTIONS = [
  "Hong Kong",
  "British Virgin Islands (BVI)",
  "Cayman Islands",
  "Singapore",
  "United Kingdom",
  "United States (Delaware)",
  "Australia",
  "Canada",
  "Japan",
  "Other",
] as const;

export const BR_NUMBER_REGEX = /^\d{8}$|^\d{11}$/;

export function validateBrNumber(br: string): boolean {
  return BR_NUMBER_REGEX.test(br.replace(/[\s-]/g, ""));
}

export interface IdentityFormData {
  clientType: ClientType;
  legalName: string;
  entityJurisdiction?: string;
  brNumber?: string;
  representativeName?: string;
  representativeTitle?: string;
  email: string;
}

export function validateIdentityForm(data: IdentityFormData): string[] {
  const errors: string[] = [];

  if (!data.legalName.trim()) {
    errors.push("Legal name is required");
  }

  if (!data.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    errors.push("A valid email address is required");
  }

  if (data.clientType === "entity") {
    if (!data.entityJurisdiction) {
      errors.push("Jurisdiction of incorporation is required");
    }
    if (data.entityJurisdiction === "Hong Kong" && data.brNumber) {
      if (!validateBrNumber(data.brNumber)) {
        errors.push("Hong Kong BR number must be 8 or 11 digits");
      }
    }
    if (!data.representativeName?.trim()) {
      errors.push("Representative name is required for entities");
    }
    if (!data.representativeTitle?.trim()) {
      errors.push("Representative title is required for entities");
    }
  }

  return errors;
}

export function getSignatureName(data: {
  client_type: ClientType;
  legal_name: string;
  representative_name: string | null;
}): string {
  return data.client_type === "entity" && data.representative_name
    ? data.representative_name
    : data.legal_name;
}

export const AGREEMENT_CHECKBOXES = [
  "I have read and understood the entire agreement above",
  "I agree to be legally bound by these terms",
  "I understand that clicking \"Sign\" constitutes my electronic signature under the Electronic Transactions Ordinance (Cap. 553)",
] as const;

export const MIN_REVIEW_SECONDS = 10;
export const VERIFICATION_CODE_LENGTH = 6;
export const VERIFICATION_EXPIRY_MINUTES = 15;
export const MAX_VERIFICATION_ATTEMPTS = 3;
export const SESSION_TIMEOUT_MINUTES = 30;
