import { CheckoutProvider } from "@/lib/checkout-context";

export default function CheckoutLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <CheckoutProvider>
      <main className="min-h-screen bg-background">
        <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </CheckoutProvider>
  );
}
