import { setRequestLocale } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/sign-in`);

  const { data: profile } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .single();

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6 lg:px-8">
      <h1 className="mb-8 text-2xl font-bold">Settings</h1>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground">Email</label>
            <p>{user.email}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Name</label>
            <p>{profile?.contact_name || "—"}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Company</label>
            <p>{profile?.company_name || "—"}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Industry</label>
            <p>{profile?.industry || "—"}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Language</label>
            <p>{profile?.language_pref || "en"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent>
          <form action={`/${locale}/auth/sign-out`} method="POST">
            <Button variant="outline" type="submit">
              Sign Out
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
