"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { Globe } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export function LocaleSwitcher() {
  const t = useTranslations("locale");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function onSelectLocale(nextLocale: string) {
    setOpen(false);
    router.replace(pathname, { locale: nextLocale as "en" | "zh-hant" | "zh-hans" });
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        aria-label={t("switchLocale")}
      >
        <Globe className="h-4 w-4" />
        <span className="hidden sm:inline">{t(locale as "en" | "zh-hant" | "zh-hans")}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[140px] rounded-md border border-border bg-popover p-1 shadow-md">
          {routing.locales.map((loc) => (
            <button
              key={loc}
              onClick={() => onSelectLocale(loc)}
              className={`w-full rounded-sm px-3 py-1.5 text-left text-sm transition-colors hover:bg-accent ${
                loc === locale ? "bg-accent font-medium" : ""
              }`}
            >
              {t(loc)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
