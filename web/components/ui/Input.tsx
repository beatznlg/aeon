"use client";

import { forwardRef, InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(({ label, error, className = "", id, ...props }, ref) => {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex w-full flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="aeon-label">
          {label}
        </label>
      )}
      <input
        id={inputId}
        ref={ref}
        className={`aeon-input ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-aeon-danger">{error}</span>}
    </div>
  );
});
Input.displayName = "Input";
export default Input;
