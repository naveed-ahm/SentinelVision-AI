import { AlertTriangle, Inbox, Loader2, RefreshCw, ShieldAlert, X } from "lucide-react";
import { useEffect } from "react";

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} />;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-muted">
      <Spinner />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-muted gap-2">
      <Inbox className="h-8 w-8 opacity-60" />
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="text-xs opacity-70">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-crit gap-2">
      <AlertTriangle className="h-8 w-8" />
      <p className="text-sm font-medium">{message}</p>
      {onRetry && (
        <button className="btn-ghost mt-2" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" /> Retry
        </button>
      )}
    </div>
  );
}

const SEVERITY_STYLES: Record<string, string> = {
  online: "bg-ok/10 text-ok border border-ok/30",
  offline: "bg-crit/10 text-crit border border-crit/30",
  error: "bg-crit/10 text-crit border border-crit/30",
  disabled: "bg-slate-500/10 text-slate-600 border border-slate-400/40",
  info: "bg-accent/10 text-accent-bright border border-accent/30",
  warning: "bg-warn/10 text-warn border border-warn/30",
  critical: "bg-crit/10 text-crit border border-crit/30",
  open: "bg-warn/10 text-warn border border-warn/30",
  acknowledged: "bg-accent/10 text-accent-bright border border-accent/30",
  resolved: "bg-ok/10 text-ok border border-ok/30",
  car: "bg-accent/10 text-accent-bright border border-accent/30",
  motorcycle: "bg-purple-500/10 text-purple-700 border border-purple-500/30",
  bus: "bg-warn/10 text-warn border border-warn/30",
  truck: "bg-orange-500/10 text-orange-700 border border-orange-500/30",
  person: "bg-teal-500/10 text-teal-700 border border-teal-500/30",
};

export function Badge({ value, className = "" }: { value: string; className?: string }) {
  const style = SEVERITY_STYLES[value.toLowerCase()] ?? "bg-slate-500/10 text-slate-600 border border-slate-400/40";
  return <span className={`badge ${style} ${className}`}>{value.replace(/_/g, " ")}</span>;
}

export function DemoBadge({ isDemo, className = "" }: { isDemo?: boolean; className?: string }) {
  if (!isDemo) return null;
  return (
    <span className={`badge bg-warn/15 text-warn border border-warn/40 uppercase tracking-wider ${className}`} title="Demonstration data — not real CCTV output">
      demo
    </span>
  );
}

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "accent",
  loading = false,
}: {
  label: string;
  value: number | string | undefined;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "accent" | "ok" | "warn" | "crit" | "muted";
  loading?: boolean;
}) {
  const tones: Record<string, string> = {
    accent: "text-accent-bright bg-accent/10",
    ok: "text-ok bg-ok/10",
    warn: "text-warn bg-warn/10",
    crit: "text-crit bg-crit/10",
    muted: "text-muted bg-slate-500/10",
  };
  return (
    <div className="card p-4 flex items-center gap-4">
      <div className={`rounded-lg p-2.5 ${tones[tone]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-muted font-semibold">{label}</p>
        {loading ? (
          <Spinner className="h-4 w-4 mt-1" />
        ) : (
          <p className="text-xl font-bold tabular-nums truncate">{value ?? "—"}</p>
        )}
      </div>
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm text-muted">
      <span>
        {total === 0 ? "No records" : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}
      </span>
      <div className="flex items-center gap-2">
        <button className="btn-ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Prev
        </button>
        <span className="tabular-nums">
          {page} / {pages}
        </span>
        <button className="btn-ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 md:p-8" onClick={onClose}>
      <div
        className={`card w-full ${wide ? "max-w-3xl" : "max-w-lg"} my-4`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="card-header sticky top-0 bg-white z-10 rounded-t-lg">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button className="text-muted hover:text-body" onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export function ShieldNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-md p-3">
      <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0 text-accent-bright" />
      <div>{children}</div>
    </div>
  );
}
