interface NeuProgressProps {
  value: number;
}

export function NeuProgress({ value }: NeuProgressProps) {
  const clamped = Math.max(0, Math.min(1, value));

  return (
    <div
      className="w-full overflow-hidden"
      style={{
        height: 8,
        borderRadius: 9999,
        background: "var(--surface-inset)",
        boxShadow:
          "inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)",
      }}
      role="progressbar"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        style={{
          width: `${clamped * 100}%`,
          height: "100%",
          borderRadius: 9999,
          background: "linear-gradient(90deg, var(--accent), var(--accent-warm))",
          transition: "width 600ms ease-out",
        }}
      />
    </div>
  );
}
