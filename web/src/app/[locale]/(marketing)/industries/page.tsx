import { setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { INDUSTRY_VERTICALS, CLIENT_PERSONAS } from "@/lib/constants";
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

const industryIcons: Record<string, React.ReactNode> = {
  "real-estate": <Building2 className="h-6 w-6" />,
  immigration: <Briefcase className="h-6 w-6" />,
  "fnb-hospitality": <UtensilsCrossed className="h-6 w-6" />,
  accounting: <Calculator className="h-6 w-6" />,
  legal: <Scale className="h-6 w-6" />,
  "medical-dental": <Stethoscope className="h-6 w-6" />,
  construction: <HardHat className="h-6 w-6" />,
  "import-export": <Ship className="h-6 w-6" />,
  "academic-researcher": <GraduationCap className="h-6 w-6" />,
  "vibe-coder": <Code className="h-6 w-6" />,
  solopreneur: <Store className="h-6 w-6" />,
  "curious-student": <BookOpen className="h-6 w-6" />,
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
          Built for Your Industry
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          Pre-loaded software tailored to Hong Kong&apos;s key business sectors
          and professional needs.
        </p>
      </div>

      <h2 className="mb-8 text-2xl font-semibold">Business Verticals</h2>
      <div className="mb-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {INDUSTRY_VERTICALS.map((industry) => (
          <Link
            key={industry.slug}
            href={`/industries/${industry.slug}` as never}
          >
            <Card className="group h-full transition-shadow hover:shadow-lg">
              <CardHeader>
                <div className="mb-3 flex items-center gap-3">
                  <div className="rounded-lg bg-primary/10 p-2 text-primary">
                    {industryIcons[industry.slug]}
                  </div>
                  <Badge variant="secondary">
                    {industry.softwareStack.length} tools
                  </Badge>
                </div>
                <CardTitle className="text-lg">{industry.name}</CardTitle>
                <CardDescription className="line-clamp-2">
                  {industry.tagline}
                </CardDescription>
                <div className="mt-3 flex items-center text-sm font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Learn more <ArrowRight className="ml-1 h-4 w-4" />
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>

      <h2 className="mb-8 text-2xl font-semibold">For Individuals</h2>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {CLIENT_PERSONAS.map((persona) => (
          <Link
            key={persona.slug}
            href={`/industries/${persona.slug}` as never}
          >
            <Card className="group h-full transition-shadow hover:shadow-lg">
              <CardHeader>
                <div className="mb-3 flex items-center gap-3">
                  <div className="rounded-lg bg-primary/10 p-2 text-primary">
                    {industryIcons[persona.slug]}
                  </div>
                  <Badge variant="secondary">
                    {persona.softwareStack.length} tools
                  </Badge>
                </div>
                <CardTitle className="text-lg">{persona.name}</CardTitle>
                <CardDescription className="line-clamp-2">
                  {persona.tagline}
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
