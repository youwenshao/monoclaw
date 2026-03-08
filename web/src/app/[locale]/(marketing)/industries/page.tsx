import { setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { TOOL_SUITES } from "@/lib/constants";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  Building2,
  Briefcase,
  UtensilsCrossed,
  Calculator,
  Scale,
  Stethoscope,
  HardHat,
  Ship,
  GraduationCap,
  Code,
  Store,
  BookOpen,
} from "lucide-react";

const toolIcons: Record<string, React.ReactNode> = {
  "real-estate": <Building2 className="h-6 w-6" />,
  immigration: <Briefcase className="h-6 w-6" />,
  "fnb-hospitality": <UtensilsCrossed className="h-6 w-6" />,
  accounting: <Calculator className="h-6 w-6" />,
  legal: <Scale className="h-6 w-6" />,
  "medical-dental": <Stethoscope className="h-6 w-6" />,
  construction: <HardHat className="h-6 w-6" />,
  "import-export": <Ship className="h-6 w-6" />,
  academic: <GraduationCap className="h-6 w-6" />,
  "vibe-coder": <Code className="h-6 w-6" />,
  solopreneur: <Store className="h-6 w-6" />,
  student: <BookOpen className="h-6 w-6" />,
};

export default async function IndustriesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="mb-16 text-center">
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
          12 Tool Suites, One Mac
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          Every Mona Mac ships with all 12 tool suites pre-installed.
          Mona automatically routes your requests to the right tool based on context.
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {TOOL_SUITES.map((suite) => (
          <Link
            key={suite.id}
            href={`/industries/${suite.id}` as never}
          >
            <Card className="group h-full transition-shadow hover:shadow-lg">
              <CardHeader>
                <div className="mb-3 flex items-center gap-3">
                  <div className="rounded-lg bg-primary/10 p-2 text-primary">
                    {toolIcons[suite.id]}
                  </div>
                  <Badge variant="secondary">
                    {suite.tools.length} tools
                  </Badge>
                </div>
                <CardTitle className="text-lg">{suite.name}</CardTitle>
                <CardDescription className="line-clamp-2">
                  {suite.description}
                </CardDescription>
                <div className="mt-3 flex items-center text-sm font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Learn more <ArrowRight className="ml-1 h-4 w-4" />
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
