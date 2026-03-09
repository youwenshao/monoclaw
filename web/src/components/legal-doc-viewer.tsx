import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface LegalDocViewerProps {
  title: string;
  html: string;
  className?: string;
  scrollableClassName?: string;
}

export function LegalDocViewer({
  title,
  html,
  className,
  scrollableClassName,
}: LegalDocViewerProps) {
  return (
    <Card className={cn("mb-6", className)}>
      <CardHeader>
        <CardTitle className="text-xl">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "prose prose-sm dark:prose-invert min-h-[400px] max-h-[75vh] overflow-y-auto rounded-md border bg-muted/30 p-6",
            scrollableClassName,
          )}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </CardContent>
    </Card>
  );
}
