import { useMemo } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface WaveFormProps {
  active?: boolean;
}

const BAR_COUNT = 48;
const BAR_WIDTH = 3;
const BAR_GAP = 2;

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export function WaveForm({ active = false }: WaveFormProps) {
  const reducedMotion = useReducedMotion();

  // Stable random seeds per bar for idle heights and animation offsets
  const barSeeds = useMemo(
    () =>
      Array.from({ length: BAR_COUNT }, () => ({
        idleHeight: randomBetween(2, 5),
        activeHeight: randomBetween(10, 30),
        delay: randomBetween(0, 0.8),
        duration: randomBetween(0.4, 0.9),
      })),
    []
  );

  return (
    <div
      className="flex items-center justify-center"
      style={{
        height: 100,
        gap: BAR_GAP,
      }}
      aria-hidden="true"
    >
      {barSeeds.map((seed, i) => {
        const idleKeyframes = [
          seed.idleHeight,
          seed.idleHeight + randomBetween(1, 3),
          seed.idleHeight,
        ];
        const activeKeyframes = [
          seed.activeHeight * 0.3,
          seed.activeHeight,
          seed.activeHeight * 0.5,
          seed.activeHeight * 0.8,
          seed.activeHeight * 0.3,
        ];

        return (
          <motion.div
            key={i}
            style={{
              width: BAR_WIDTH,
              borderRadius: 9999,
              background: "var(--accent)",
            }}
            animate={
              reducedMotion
                ? { height: active ? seed.activeHeight * 0.6 : seed.idleHeight }
                : {
                    height: active ? activeKeyframes : idleKeyframes,
                    transition: {
                      duration: active ? seed.duration : 2 + seed.delay,
                      repeat: Infinity,
                      ease: "easeInOut",
                      delay: seed.delay,
                    },
                  }
            }
            transition={{ duration: 0.3, ease: "easeOut" }}
          />
        );
      })}
    </div>
  );
}
