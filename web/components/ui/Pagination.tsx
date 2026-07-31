"use client";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
  className?: string;
}

export default function Pagination({
  page,
  pageSize,
  total,
  onChange,
  className = "",
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className={`flex flex-col items-center justify-between gap-3 sm:flex-row ${className}`}>
      <span className="text-xs text-aeon-fg-mute">
        Showing {start}-{end} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="rounded-aeon-sm border border-aeon-border bg-aeon-bg px-3 py-1.5 text-sm text-aeon-fg-soft transition-colors hover:bg-aeon-bg-2 disabled:opacity-50"
        >
          ← Prev
        </button>
        <span className="min-w-[4rem] text-center text-sm text-aeon-fg-soft">
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => onChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="rounded-aeon-sm border border-aeon-border bg-aeon-bg px-3 py-1.5 text-sm text-aeon-fg-soft transition-colors hover:bg-aeon-bg-2 disabled:opacity-50"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
