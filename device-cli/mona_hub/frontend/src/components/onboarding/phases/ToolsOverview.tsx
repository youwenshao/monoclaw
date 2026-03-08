import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { PageTransition, FadeUp, NeuCard, NeuButton } from "@/components/ui";
import { getInstalledTools, getClawHubSkills } from "@/lib/api";
import type { ToolInfo } from "@/lib/api";
import { childVariants } from "@/lib/animations";

interface ClawHubSkill {
  slug: string;
  name: string;
  description?: string;
}

const staggerContainer = {
  enter: {
    transition: { staggerChildren: 0.1 },
  },
};

const cardVariants = {
  initial: { opacity: 0, x: 40 },
  enter: { opacity: 1, x: 0, transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] as const } },
};

export function ToolsOverview() {
  const navigate = useNavigate();
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [skills, setSkills] = useState<ClawHubSkill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([getInstalledTools(), getClawHubSkills()]).then(
      ([toolsResult, skillsResult]) => {
        if (toolsResult.status === "fulfilled") {
          setTools(toolsResult.value);
        }
        if (skillsResult.status === "fulfilled" && Array.isArray(skillsResult.value)) {
          setSkills(skillsResult.value as ClawHubSkill[]);
        }
        setLoading(false);
      },
    );
  }, []);

  return (
    <PageTransition>
      <FadeUp>
        <h2 className="mb-2 text-2xl font-light text-text-primary">
          Here's what we can do together.
        </h2>
      </FadeUp>

      <FadeUp className="mb-4">
        <p className="text-sm text-text-secondary">
          All 12 tool suites are pre-installed on your Mac. I automatically
          route your requests to the right tool, or you can pick one
          with a slash command like <code className="rounded bg-white/5 px-1.5 py-0.5 text-accent">/real-estate</code>.
        </p>
      </FadeUp>

      <FadeUp className="mb-8">
        <span className="inline-block rounded-full bg-accent/10 px-3 py-1 text-sm text-accent">
          {loading ? "..." : `${tools.length} tool suites installed`}
        </span>
      </FadeUp>

      {/* Tool Suites */}
      {tools.length > 0 && (
        <FadeUp className="mb-10">
          <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-tertiary">
            Your Tools
          </h3>
          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="enter"
            className="-mx-6 flex snap-x snap-mandatory gap-4 overflow-x-auto px-6 pb-4 sm:-mx-12 sm:px-12"
            style={{ scrollbarWidth: "none" }}
          >
            {tools.map((tool) => (
              <motion.div
                key={tool.slug}
                variants={cardVariants}
                className="snap-start"
              >
                <NeuCard
                  variant="raised"
                  padding="md"
                  className="w-72 flex-shrink-0"
                >
                  <h3 className="text-lg font-medium text-text-primary">
                    {tool.name}
                  </h3>
                  {tool.description && (
                    <p className="mt-1 text-sm text-text-secondary">
                      {tool.description}
                    </p>
                  )}

                  {tool.tools.length > 0 && (
                    <>
                      <div className="my-4 h-px bg-white/5" />
                      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-accent">
                        Capabilities
                      </p>
                      <ul className="space-y-1">
                        {tool.tools.map((t) => (
                          <li
                            key={t}
                            className="flex items-start gap-2 text-sm text-text-secondary"
                          >
                            <span className="mt-0.5 text-accent">•</span>
                            {t}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </NeuCard>
              </motion.div>
            ))}
          </motion.div>
        </FadeUp>
      )}

      {/* Community Skills */}
      {skills.length > 0 && (
        <FadeUp className="mb-10">
          <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-tertiary">
            Community Skills
          </h3>
          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="enter"
            className="-mx-6 flex snap-x snap-mandatory gap-4 overflow-x-auto px-6 pb-4 sm:-mx-12 sm:px-12"
            style={{ scrollbarWidth: "none" }}
          >
            {skills.map((skill) => (
              <motion.div
                key={skill.slug}
                variants={cardVariants}
                className="snap-start"
              >
                <NeuCard
                  variant="raised"
                  padding="md"
                  className="w-64 flex-shrink-0"
                >
                  <h3 className="text-base font-medium text-text-primary">
                    {skill.name}
                  </h3>
                  {skill.description && (
                    <p className="mt-1 text-sm text-text-secondary">
                      {skill.description}
                    </p>
                  )}
                </NeuCard>
              </motion.div>
            ))}
          </motion.div>
        </FadeUp>
      )}

      {loading && tools.length === 0 && skills.length === 0 && (
        <FadeUp className="mb-10">
          <div className="flex items-center justify-center py-12">
            <motion.div
              className="h-6 w-6 rounded-full border-2 border-accent/30 border-t-accent"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            />
          </div>
        </FadeUp>
      )}

      <FadeUp className="mb-6">
        <p className="text-center text-sm text-text-tertiary">
          Mona can find and install new skills anytime — just ask.
        </p>
      </FadeUp>

      <motion.div
        variants={childVariants}
        initial="initial"
        animate="enter"
        className="flex justify-center"
      >
        <NeuButton onClick={() => navigate("/welcome/first-task")}>
          Try it out →
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
