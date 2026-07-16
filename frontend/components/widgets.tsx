"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardBody, CardHeader } from "@/components/ui";
import { cn, fmt } from "@/lib/utils";

const AXIS = { stroke: "#3a4658", fontSize: 10 };
const GRID = "#1e2733";

export function StatCard({
  label,
  value,
  sub,
  tone = "fg",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "fg" | "pos" | "neg" | "accent" | "warn";
}) {
  const tones: Record<string, string> = {
    fg: "text-fg",
    pos: "text-pos",
    neg: "text-neg",
    accent: "text-accent",
    warn: "text-warn",
  };
  return (
    <Card>
      <CardBody className="py-3">
        <div className="text-[10px] uppercase tracking-[0.12em] text-muted">{label}</div>
        <div className={cn("num mt-1 text-2xl font-semibold", tones[tone])}>{value}</div>
        {sub && <div className="mt-0.5 text-[11px] text-muted">{sub}</div>}
      </CardBody>
    </Card>
  );
}

export function Panel({
  title,
  right,
  children,
  className,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader title={title} right={right} />
      <CardBody>{children}</CardBody>
    </Card>
  );
}

export function EmptyLive({ note }: { note: string }) {
  return (
    <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
      <div className="text-sm text-muted">No live data</div>
      <div className="max-w-xs text-[11px] leading-relaxed text-muted/70">{note}</div>
    </div>
  );
}

const tip = {
  contentStyle: {
    background: "#0f141c",
    border: "1px solid #1e2733",
    borderRadius: 8,
    fontSize: 12,
  },
  labelStyle: { color: "#6b7785" },
};

export function HistChart({
  data,
  color = "#22d3ee",
}: {
  data: { bucket: string; count: number }[];
  color?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="bucket" {...AXIS} tickLine={false} />
        <YAxis {...AXIS} tickLine={false} allowDecimals={false} />
        <Tooltip {...tip} cursor={{ fill: "#ffffff08" }} />
        <Bar dataKey="count" fill={color} radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function FunnelBars({ data }: { data: { stage: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="flex flex-col gap-1.5">
      {data.map((d) => (
        <div key={d.stage} className="flex items-center gap-2">
          <div className="w-24 text-right text-[11px] capitalize text-muted">{d.stage}</div>
          <div className="h-5 flex-1 overflow-hidden rounded bg-panel2">
            <div
              className="h-full rounded bg-accent/70"
              style={{ width: `${(d.count / max) * 100}%` }}
            />
          </div>
          <div className="num w-10 text-right text-xs">{fmt.int(d.count)}</div>
        </div>
      ))}
    </div>
  );
}

export function AreaSeries({
  data,
  color = "#34d399",
}: {
  data: { t: string; v: number }[];
  color?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.4} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="t" {...AXIS} tickLine={false} />
        <YAxis {...AXIS} tickLine={false} />
        <Tooltip {...tip} />
        <Area dataKey="v" stroke={color} fill="url(#g)" strokeWidth={1.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function Heatmap({
  cells,
}: {
  cells: { family: string; symbol: string; tested: number; best_dsr: number }[];
}) {
  const families = [...new Set(cells.map((c) => c.family))];
  const symbols = [...new Set(cells.map((c) => c.symbol))];
  const lookup = new Map(cells.map((c) => [`${c.family}|${c.symbol}`, c]));
  const shade = (d: number) => `rgba(34,211,238,${Math.min(0.85, 0.1 + d)})`;
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-1 text-[10px]">
        <thead>
          <tr>
            <th />
            {symbols.map((s) => (
              <th key={s} className="px-1 text-muted">{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {families.map((f) => (
            <tr key={f}>
              <td className="pr-2 text-right capitalize text-muted">{f}</td>
              {symbols.map((s) => {
                const c = lookup.get(`${f}|${s}`);
                return (
                  <td
                    key={s}
                    title={c ? `${f}/${s} · dsr ${c.best_dsr}` : ""}
                    className="num h-7 w-12 rounded text-center"
                    style={{ background: c ? shade(c.best_dsr) : "#0f141c" }}
                  >
                    {c ? c.best_dsr.toFixed(2) : ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LimitBar({ name, used, limit }: { name: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(1, used / limit) : 0;
  const tone = pct > 0.9 ? "bg-neg" : pct > 0.7 ? "bg-warn" : "bg-pos";
  return (
    <div className="flex items-center gap-3">
      <div className="w-40 text-xs text-muted">{name}</div>
      <div className="h-2 flex-1 overflow-hidden rounded bg-panel2">
        <div className={cn("h-full", tone)} style={{ width: `${pct * 100}%` }} />
      </div>
      <div className="num w-24 text-right text-[11px] text-muted">
        {fmt.num(used, 2)} / {fmt.num(limit, 2)}
      </div>
    </div>
  );
}
