"use client";

import { ReactNode, useEffect } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export default function Modal({ open, onClose, title, children, footer, className = "" }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={`relative z-10 w-full max-w-lg overflow-hidden rounded-aeon border border-aeon-border bg-aeon-bg-1 shadow-aeon-lg ${className}`}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-aeon-border px-5 py-4">
            <h3 className="text-base font-semibold text-aeon-fg">{title}</h3>
            <button
              onClick={onClose}
              className="text-aeon-fg-mute transition-colors hover:text-aeon-fg"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        )}
        <div className="p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-aeon-border px-5 py-4">{footer}</div>}
      </div>
    </div>
  );
}
