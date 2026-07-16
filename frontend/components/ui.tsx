import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-panel shadow-panel",
        className,
      )}
      {...p}
    />
  );
}

export function CardHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
        {title}
      </h3>
      {right}
    </div>
  );
}

export function CardBody({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...p} />;
}

export function Badge({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "pos" | "neg" | "warn" | "accent";
}) {
  const tones: Record<string, string> = {
    muted: "bg-panel2 text-muted border-border",
    pos: "bg-pos/10 text-pos border-pos/30",
    neg: "bg-neg/10 text-neg border-neg/30",
    warn: "bg-warn/10 text-warn border-warn/30",
    accent: "bg-accent/10 text-accent border-accent/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border/50 hover:bg-panel2/50">
              {r.map((c, j) => (
                <td key={j} className="px-3 py-1.5 num">{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div className="py-6 text-center text-xs text-muted">no rows</div>
      )}
    </div>
  );
}
