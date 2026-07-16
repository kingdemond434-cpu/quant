"use client";

import { usePoll } from "@/lib/api";
import type { RiskDashboard } from "@/lib/types";
import { Badge } from "@/components/ui";
import { LimitBar, Panel, StatCard } from "@/components/widgets";
import { fmt } from "@/lib/utils";

export default function RiskPage() {
  const { data } = usePoll<RiskDashboard>("/api/risk", 5000);

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Risk</h1>
        {data?.kill_switch_active ? (
          <Badge tone="neg">kill-switch active</Badge>
        ) : (
          <Badge tone="pos">nominal</Badge>
        )}
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="VaR (95%)" value={data ? fmt.pct(data.var_95) : "—"} tone="warn" />
        <StatCard
          label="Expected Shortfall"
          value={data ? fmt.pct(data.expected_shortfall) : "—"}
          tone="neg"
        />
        <StatCard
          label="Kill Switch"
          value={data?.kill_switch_active ? "ON" : "OFF"}
          tone={data?.kill_switch_active ? "neg" : "pos"}
          sub={data?.kill_reason || "no halt"}
        />
        <StatCard
          label="Mode"
          value={data?.live ? "LIVE" : "RESEARCH"}
          tone={data?.live ? "pos" : "warn"}
        />
      </div>

      <Panel title="Risk Limits" right={<span className="text-[10px] text-muted">used / limit</span>}>
        <div className="space-y-3">
          {(data?.limits ?? []).map((l) => (
            <LimitBar key={l.name} name={l.name} used={l.used} limit={l.limit} />
          ))}
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-muted">
          Limits reflect the framework defaults (risk overrides alpha: no order without a risk
          approval). Utilization is zero with no live book.
        </p>
      </Panel>
    </div>
  );
}
