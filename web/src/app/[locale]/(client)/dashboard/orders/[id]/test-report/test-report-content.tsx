"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import type { Order, Device, DeviceTestResult, DeviceTestSummary, TestCategory } from "@/types/database";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, Check, X, AlertTriangle, SkipForward, Clock } from "lucide-react";

const CATEGORY_LABELS: Record<TestCategory, string> = {
  hardware: "Hardware",
  macos_environment: "macOS",
  openclaw_core: "OpenClaw Core",
  llm_models: "LLM Models",
  voice_system: "Voice",
  security: "Security",
  stress_edge_cases: "Stress & Edge",
};

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "pass":
      return <Check className="h-4 w-4 text-green-600" />;
    case "fail":
      return <X className="h-4 w-4 text-red-600" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
    case "skipped":
      return <SkipForward className="h-4 w-4 text-muted-foreground" />;
    default:
      return null;
  }
}

function statusBadgeColor(status: string): "default" | "destructive" | "secondary" | "outline" {
  switch (status) {
    case "pass": return "default";
    case "fail": return "destructive";
    case "warning": return "outline";
    default: return "secondary";
  }
}

export function TestReportContent({
  order,
  device,
  testResults,
  testSummary,
}: {
  order: Order;
  device: Device;
  testResults: DeviceTestResult[];
  testSummary: DeviceTestSummary | null;
}) {
  const t = useTranslations("dashboard");

  const categories = Object.keys(CATEGORY_LABELS) as TestCategory[];
  const passRate = testSummary
    ? Math.round((testSummary.passed / testSummary.total_tests) * 100)
    : 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Button variant="ghost" asChild size="sm">
          <Link href={`/dashboard/orders/${order.id}` as never}>
            <ArrowLeft className="mr-2 h-4 w-4" /> {t("orderDetails")}
          </Link>
        </Button>
      </div>

      <h1 className="mb-2 text-2xl font-bold">{t("testReport")}</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Device: {device.serial_number || "N/A"} &middot; {device.hardware_type}
      </p>

      {testSummary && (
        <div className="mb-8 grid gap-4 sm:grid-cols-5">
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold">{passRate}%</p>
              <p className="text-xs text-muted-foreground">{t("overallStatus")}</p>
              <Progress value={passRate} className="mt-2" />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-green-600">{testSummary.passed}</p>
              <p className="text-xs text-muted-foreground">{t("passed")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-red-600">{testSummary.failed}</p>
              <p className="text-xs text-muted-foreground">{t("failed")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-yellow-600">{testSummary.warnings}</p>
              <p className="text-xs text-muted-foreground">{t("warnings")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-3xl font-bold text-muted-foreground">{testSummary.skipped}</p>
              <p className="text-xs text-muted-foreground">{t("skipped")}</p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t("testCategories")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="hardware">
            <TabsList className="mb-4 flex flex-wrap gap-1">
              {categories.map((cat) => {
                const results = testResults.filter((r) => r.category === cat);
                const failed = results.filter((r) => r.status === "fail").length;
                return (
                  <TabsTrigger key={cat} value={cat} className="text-xs">
                    {CATEGORY_LABELS[cat]}
                    {failed > 0 && (
                      <span className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-red-100 text-[10px] text-red-700">
                        {failed}
                      </span>
                    )}
                  </TabsTrigger>
                );
              })}
            </TabsList>

            {categories.map((cat) => {
              const results = testResults.filter((r) => r.category === cat);
              return (
                <TabsContent key={cat} value={cat}>
                  {results.length === 0 ? (
                    <p className="py-8 text-center text-muted-foreground">
                      No test results in this category yet.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {results.map((result) => (
                        <div
                          key={result.id}
                          className="flex items-center justify-between rounded-lg border p-3"
                        >
                          <div className="flex items-center gap-3">
                            <StatusIcon status={result.status} />
                            <div>
                              <p className="text-sm font-medium">{result.test_name}</p>
                              {result.details && Object.keys(result.details).length > 0 && (
                                <p className="text-xs text-muted-foreground">
                                  {JSON.stringify(result.details).slice(0, 120)}
                                  {JSON.stringify(result.details).length > 120 ? "..." : ""}
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            {result.duration_ms != null && (
                              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                {result.duration_ms}ms
                              </span>
                            )}
                            <Badge variant={statusBadgeColor(result.status)}>
                              {result.status}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>
              );
            })}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
