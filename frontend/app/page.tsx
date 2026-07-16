"use client";

import { usePoll } from "@/lib/api";
import type { Overview } from "@/lib/types";
import { Badge } from "@/components/ui";
import { Panel, StatCard } from "@/components/widgets";
import { fmt } from "@/lib/utils";

export default function OverviewPage() {
  const { data, updatedAt, error } = usePoll<Overview>("/api/overview", 5000);

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Executive Overview</h1>
          <p className="text-xs text-muted">Real-time research &amp; risk posture</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted">
          {error ? (
            <Badge tone="neg">api offline</Badge>
          ) : data?.live ? (
            <Badge tone="pos">live</Badge>
          ) : (
            <Badge tone="warn">research mode</Badge>
          )}
          <span className="num">
            {updatedAt ? updatedAt.toLocaleTimeString() : "—"}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard
          label="Alpha Score"
          value={data ? fmt.num(data.alpha_score, 1) : "—"}
          tone="accent"
          sub="best deflated-Sharpe × 100"
        />
        <StatCard
          label="Survivors"
          value={data ? fmt.int(data.survivors) : "—"}
          tone={data && data.survivors > 0 ? "pos" : "fg"}
          sub="net-of-cost, REGISTRY"
        />
        <StatCard
          label="Active Campaigns"
          value={data ? fmt.int(data.active_campaigns) : "—"}
        />
        <StatCard
          label="Live PnL"
          value={data ? fmt.money(data.live_pnl) : "—"}
          tone={data && data.live_pnl < 0 ? "neg" : "fg"}
          sub={data?.live ? "" : "no live book"}
        />
        <StatCard
          label="Risk Utilization"
          value={data ? fmt.pct(data.risk_utilization) : "—"}
          tone="fg"
        />
        <StatCard
          label="Research Velocity"
          value={data ? `${fmt.int(data.research_velocity)}/d` : "—"}
          sub="candidates tested / 24h"
        />
      </div>

      <Panel title="Headline Metrics">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(data?.kpis ?? []).map((k) => (
            <div key={k.label} className="rounded-md border border-border bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wide text-muted">{k.label}</div>
              <div className="num mt-1 text-lg">{fmt.num(k.value, 3)}</div>
              <div className="text-[11px] text-muted">{k.hint}</div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-muted">
          The platform reports validated survivors, not backtests run. A score reflects the best
          candidate that survived the full net-of-cost gauntlet; zero survivors is an honest,
          acceptable outcome.
        </p>
      </Panel>
    </div>
  );
}
