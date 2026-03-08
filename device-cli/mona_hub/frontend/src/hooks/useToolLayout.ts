import { useState, useCallback, useEffect } from "react";
import type { ToolInfo } from "@/lib/api";

const STORAGE_KEY = "mona-tool-layout";

interface ToolLayout {
  order: string[];
  hidden: string[];
}

function readLayout(): ToolLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        order: Array.isArray(parsed.order) ? parsed.order : [],
        hidden: Array.isArray(parsed.hidden) ? parsed.hidden : [],
      };
    }
  } catch {
    // corrupt storage
  }
  return { order: [], hidden: [] };
}

function writeLayout(layout: ToolLayout) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
}

/**
 * Merge persisted layout with live tool data from the API.
 * - Tools in the saved order come first.
 * - New tools (added after the layout was saved) are appended at the end.
 * - Stale slugs (tools removed from the device) are dropped.
 */
function mergeWithLiveData(layout: ToolLayout, tools: ToolInfo[]): ToolLayout {
  const liveSlugs = new Set(tools.map((t) => t.slug));

  const order = layout.order.filter((s) => liveSlugs.has(s));
  const ordered = new Set(order);
  for (const tool of tools) {
    if (!ordered.has(tool.slug)) {
      order.push(tool.slug);
    }
  }

  const hidden = layout.hidden.filter((s) => liveSlugs.has(s));

  return { order, hidden };
}

export function useToolLayout(tools: ToolInfo[]) {
  const [layout, setLayout] = useState<ToolLayout>(() => {
    const saved = readLayout();
    if (tools.length > 0) return mergeWithLiveData(saved, tools);
    return saved;
  });

  useEffect(() => {
    if (tools.length === 0) return;
    setLayout((prev) => mergeWithLiveData(prev, tools));
  }, [tools]);

  useEffect(() => {
    if (layout.order.length > 0) {
      writeLayout(layout);
    }
  }, [layout]);

  const reorderTools = useCallback((newOrder: string[]) => {
    setLayout((prev) => ({ ...prev, order: newOrder }));
  }, []);

  const toggleToolVisibility = useCallback((slug: string) => {
    setLayout((prev) => {
      const hidden = prev.hidden.includes(slug)
        ? prev.hidden.filter((s) => s !== slug)
        : [...prev.hidden, slug];
      return { ...prev, hidden };
    });
  }, []);

  const resetLayout = useCallback(() => {
    const defaultOrder = tools.map((t) => t.slug);
    const fresh = { order: defaultOrder, hidden: [] };
    setLayout(fresh);
  }, [tools]);

  const visibleTools = layout.order.filter((s) => !layout.hidden.includes(s));
  const hiddenTools = layout.order.filter((s) => layout.hidden.includes(s));

  return {
    toolOrder: layout.order,
    visibleTools,
    hiddenTools,
    hiddenSlugs: layout.hidden,
    reorderTools,
    toggleToolVisibility,
    resetLayout,
  };
}
