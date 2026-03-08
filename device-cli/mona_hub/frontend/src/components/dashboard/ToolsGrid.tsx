import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { NeuButton } from "@/components/ui";
import { ToolCard } from "./ToolCard";
import { useToolLayout } from "@/hooks/useToolLayout";
import { getInstalledTools, type ToolInfo } from "@/lib/api";
import { containerVariants, childVariants } from "@/lib/animations";

function SortableToolCard({
  tool,
  editing,
  hidden,
  onClick,
  onToggleVisibility,
}: {
  tool: ToolInfo;
  editing: boolean;
  hidden: boolean;
  onClick: () => void;
  onToggleVisibility: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tool.slug, disabled: !editing });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <ToolCard
      ref={setNodeRef}
      tool={tool}
      editing={editing}
      hidden={hidden}
      isDragging={isDragging}
      dragListeners={listeners}
      dragAttributes={attributes}
      style={style}
      onClick={onClick}
      onToggleVisibility={onToggleVisibility}
    />
  );
}

export function ToolsGrid() {
  const navigate = useNavigate();
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);

  const {
    visibleTools,
    hiddenTools,
    hiddenSlugs,
    reorderTools,
    toggleToolVisibility,
    resetLayout,
    toolOrder,
  } = useToolLayout(tools);

  useEffect(() => {
    getInstalledTools()
      .then((data) => {
        setTools(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;

      const oldIndex = toolOrder.indexOf(active.id as string);
      const newIndex = toolOrder.indexOf(over.id as string);
      if (oldIndex === -1 || newIndex === -1) return;

      const newOrder = [...toolOrder];
      newOrder.splice(oldIndex, 1);
      newOrder.splice(newIndex, 0, active.id as string);
      reorderTools(newOrder);
    },
    [toolOrder, reorderTools],
  );

  const toolMap = new Map(tools.map((t) => [t.slug, t]));

  const visibleToolInfos = visibleTools
    .map((slug) => toolMap.get(slug))
    .filter((t): t is ToolInfo => t !== undefined);

  const hiddenToolInfos = hiddenTools
    .map((slug) => toolMap.get(slug))
    .filter((t): t is ToolInfo => t !== undefined);

  return (
    <div className="px-6 py-8 sm:px-8">
      <motion.div
        variants={containerVariants}
        initial="initial"
        animate="enter"
        className="mx-auto max-w-[1080px]"
      >
        <motion.div variants={childVariants} className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-light text-text-primary">Tools</h1>
            <p className="mt-1 text-sm text-text-secondary">
              {tools.length} tool suites installed
            </p>
          </div>
          <div className="flex items-center gap-3">
            {editing && (
              <NeuButton
                variant="ghost"
                size="sm"
                onClick={() => {
                  resetLayout();
                  setEditing(false);
                }}
              >
                Reset
              </NeuButton>
            )}
            <NeuButton
              variant={editing ? "primary" : "secondary"}
              size="sm"
              onClick={() => setEditing((v) => !v)}
            >
              {editing ? "Done" : "Edit Layout"}
            </NeuButton>
          </div>
        </motion.div>

        {loading && tools.length === 0 && (
          <motion.div variants={childVariants} className="flex items-center justify-center py-20">
            <motion.div
              className="h-6 w-6 rounded-full border-2 border-accent/30 border-t-accent"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            />
          </motion.div>
        )}

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={visibleTools} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {visibleToolInfos.map((tool) => (
                <SortableToolCard
                  key={tool.slug}
                  tool={tool}
                  editing={editing}
                  hidden={false}
                  onClick={() => navigate(`/?tool=${tool.slug}`)}
                  onToggleVisibility={() => toggleToolVisibility(tool.slug)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        <AnimatePresence>
          {editing && hiddenToolInfos.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              transition={{ duration: 0.3 }}
              className="mt-10"
            >
              <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-tertiary">
                Hidden
              </h2>
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {hiddenToolInfos.map((tool) => (
                  <ToolCard
                    key={tool.slug}
                    tool={tool}
                    editing={editing}
                    hidden
                    onClick={() => {}}
                    onToggleVisibility={() => toggleToolVisibility(tool.slug)}
                  />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {!loading && tools.length === 0 && (
          <motion.div variants={childVariants} className="py-20 text-center">
            <p className="text-text-secondary">No tools installed yet.</p>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
