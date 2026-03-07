import { forwardRef, type InputHTMLAttributes } from "react";

interface NeuInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  className?: string;
}

export const NeuInput = forwardRef<HTMLInputElement, NeuInputProps>(
  function NeuInput({ label, className = "", ...rest }, ref) {
    const inputId = rest.id ?? (label ? `neu-input-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);

    return (
      <div className={`flex flex-col gap-1.5 ${className}`}>
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm text-text-secondary font-sans"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className="w-full border-0 outline-none font-sans text-text-primary placeholder:text-text-tertiary"
          style={{
            height: 48,
            padding: "0 16px",
            borderRadius: 8,
            fontSize: 16,
            fontWeight: 400,
            background: "var(--surface-inset)",
            boxShadow:
              "inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)",
            transition: "box-shadow 200ms ease-out",
          }}
          onFocus={(e) => {
            e.currentTarget.style.boxShadow =
              "inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light), 0 0 0 3px rgba(124, 154, 142, 0.3)";
            rest.onFocus?.(e);
          }}
          onBlur={(e) => {
            e.currentTarget.style.boxShadow =
              "inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)";
            rest.onBlur?.(e);
          }}
          {...rest}
        />
      </div>
    );
  }
);
