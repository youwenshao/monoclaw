import { Resend } from "resend";

let _resend: Resend | null = null;

function getResend(): Resend {
  if (!_resend) {
    _resend = new Resend(process.env.RESEND_API_KEY!);
  }
  return _resend;
}

const FROM_EMAIL =
  process.env.RESEND_FROM_EMAIL ||
  "Native Signing System <contracts@sentimento.tech>";
const ADMIN_BCC = process.env.ADMIN_EMAIL || "team@sentimento.dev";

export async function sendVerificationCode(
  email: string,
  code: string,
): Promise<{ success: boolean; error?: string }> {
  try {
    const { error } = await getResend().emails.send({
      from: FROM_EMAIL,
      to: email,
      subject: "Native Signing System - Verification Code",
      text: `Your verification code is: ${code}\n\nThis code expires in 15 minutes.\n\nIf you did not request this code, please ignore this email.\n\n— Sentimento Technologies Limited`,
      html: `
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
          <h2 style="margin: 0 0 8px; font-size: 20px; color: #111;">Verification Code</h2>
          <p style="margin: 0 0 24px; color: #666; font-size: 14px;">Enter this code to verify your email for contract signing.</p>
          <div style="background: #f4f4f5; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 24px;">
            <span style="font-family: monospace; font-size: 32px; letter-spacing: 0.3em; font-weight: bold; color: #111;">${code}</span>
          </div>
          <p style="margin: 0; color: #999; font-size: 12px;">This code expires in 15 minutes. If you did not request this, please ignore this email.</p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
          <p style="margin: 0; color: #999; font-size: 12px;">Sentimento Technologies Limited</p>
        </div>
      `,
    });
    if (error) return { success: false, error: error.message };
    return { success: true };
  } catch (err) {
    console.error("Failed to send verification email:", err);
    return { success: false, error: "Email delivery failed" };
  }
}

export async function sendSignedContract(
  email: string,
  legalName: string,
  contractId: string,
  pdfBuffer: Uint8Array,
): Promise<{ success: boolean; error?: string }> {
  try {
    const { error } = await getResend().emails.send({
      from: FROM_EMAIL,
      to: email,
      bcc: ADMIN_BCC,
      subject: `Contract Executed - ${contractId.slice(0, 8)}`,
      html: `
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <h2 style="margin: 0 0 8px; font-size: 20px; color: #111;">Contract Signed Successfully</h2>
          <p style="margin: 0 0 24px; color: #666; font-size: 14px;">Dear ${legalName},</p>
          <p style="margin: 0 0 16px; color: #333; font-size: 14px;">Your service agreement has been signed and executed. A copy is attached to this email for your records.</p>
          <div style="background: #f4f4f5; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
            <p style="margin: 0 0 4px; color: #666; font-size: 12px;">Contract ID</p>
            <p style="margin: 0; font-family: monospace; font-size: 14px; color: #111;">${contractId}</p>
          </div>
          <p style="margin: 0 0 16px; color: #333; font-size: 14px;">You may now proceed to complete your payment. Once payment is confirmed, we will begin provisioning your device.</p>
          <p style="margin: 0; color: #999; font-size: 12px;">Please retain this email and the attached PDF as your record of the executed agreement.</p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
          <p style="margin: 0; color: #999; font-size: 12px;">Sentimento Technologies Limited &middot; Hong Kong</p>
        </div>
      `,
      attachments: [
        {
          filename: `contract-${contractId.slice(0, 8)}.pdf`,
          content: Buffer.from(pdfBuffer).toString("base64"),
        },
      ],
    });
    if (error) return { success: false, error: error.message };
    return { success: true };
  } catch (err) {
    console.error("Failed to send contract email:", err);
    return { success: false, error: "Email delivery failed" };
  }
}
