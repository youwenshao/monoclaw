import { useEffect, useRef, useState, useCallback } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface TypeWriterProps {
  lines: string[];
  onComplete?: () => void;
  lineClassName?: string;
  pauseBetweenLines?: number;
}

function charDelay(char: string): number {
  if (char === ".") return 400;
  if (char === "?") return 350;
  if (char === ",") return 200;
  return 40 + Math.random() * 40;
}

export function TypeWriter({
  lines,
  onComplete,
  lineClassName = "",
  pauseBetweenLines = 300,
}: TypeWriterProps) {
  const reducedMotion = useReducedMotion();
  const [visibleLines, setVisibleLines] = useState<string[]>([]);
  const [currentLineIdx, setCurrentLineIdx] = useState(0);
  const [currentCharIdx, setCurrentCharIdx] = useState(0);
  const [done, setDone] = useState(false);
  const [cursorVisible, setCursorVisible] = useState(true);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // If reduced motion, show everything immediately
  useEffect(() => {
    if (reducedMotion) {
      setVisibleLines([...lines]);
      setDone(true);
      onCompleteRef.current?.();
    }
  }, [reducedMotion, lines]);

  const tick = useCallback(() => {
    if (reducedMotion || done) return;

    if (currentLineIdx >= lines.length) {
      setDone(true);
      onCompleteRef.current?.();
      return;
    }

    const line = lines[currentLineIdx];
    if (currentCharIdx <= line.length) {
      setVisibleLines((prev) => {
        const next = [...prev];
        next[currentLineIdx] = line.slice(0, currentCharIdx);
        return next;
      });

      if (currentCharIdx < line.length) {
        const delay = charDelay(line[currentCharIdx]);
        const timer = setTimeout(() => {
          setCurrentCharIdx((c) => c + 1);
        }, delay);
        return () => clearTimeout(timer);
      }

      // Line complete, move to next after pause
      const timer = setTimeout(() => {
        setCurrentLineIdx((l) => l + 1);
        setCurrentCharIdx(0);
      }, pauseBetweenLines);
      return () => clearTimeout(timer);
    }
  }, [currentLineIdx, currentCharIdx, lines, pauseBetweenLines, reducedMotion, done]);

  useEffect(() => tick(), [tick]);

  // Cursor blink
  useEffect(() => {
    if (done) return;
    const interval = setInterval(() => setCursorVisible((v) => !v), 530);
    return () => clearInterval(interval);
  }, [done]);

  return (
    <div className="relative">
      {/* Visual output (hidden from screen readers) */}
      <div aria-hidden="true">
        {visibleLines.map((text, i) => (
          <p key={i} className={lineClassName}>
            {text}
            {i === currentLineIdx && !done && (
              <motion.span
                className="inline-block align-middle"
                style={{
                  width: 2,
                  height: "1em",
                  background: "var(--accent)",
                  marginLeft: 1,
                }}
                animate={done ? { opacity: 0 } : { opacity: cursorVisible ? 1 : 0 }}
                transition={{ duration: done ? 0.3 : 0.05 }}
              />
            )}
          </p>
        ))}
      </div>

      {/* Screen reader output */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {done ? lines.join(" ") : ""}
      </div>
    </div>
  );
}
