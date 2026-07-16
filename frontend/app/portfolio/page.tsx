"use client";

import { usePoll } from "@/lib/api";
import type { PortfolioDashboard } from "@/lib/types";
import { Badge, Table } from "@/components/ui";
import { AreaSeries, EmptyLive, Panel } from "@/components/widgets";
import { fmt } from "@/lib/utils";

const NOTE =
  "No live book: zero survivors have been promoted to capital. Equity, exposure, correlation, and Kelly allocations populate once a strategy clears the deployable bar and is funded.";

export default function PortfolioPage() {
  const { data } = usePoll<PortfolioDashboard>("/api/portfolio", 5000);
  const live = data?.live ?? false;

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Portfolio</h1>
        <Badge tone={live ? "pos" : "warn"}>{live ? "live" : "no live book"}</Badge>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Equity Curve">
          {live ? <AreaSeries data={data!.equity_curve} color="#34d399" /> : <EmptyLive note={NOTE} />}
        </Panel>
        <Panel title="Drawdown">
          {live ? <AreaSeries data={data!.drawdown} color="#f87171" /> : <EmptyLive note={NOTE} />}
        </Panel>
        <Panel title="Exposure">
          {live ? (
            <Table
              head={["Sleeve", "Weight"]}
              rows={data!.exposure.map((e) => [e.name, fmt.pct(e.weight)])}
            />
          ) : (
            <EmptyLive note={NOTE} />
          )}
        </Panel>
        <Panel title="Kelly Allocation">
          {live ? (
            <Table
              head={["Strategy", "Fraction of Kelly"]}
              rows={data!.kelly.map((k) => [k.name, fmt.num(k.fraction, 3)])}
            />
          ) : (
            <EmptyLive note="Base sizing is 1/3 Kelly; half-Kelly is earned only by a walk-forward-proven, high-ROI, scalable strategy. Nothing qualifies yet." />
          )}
        </Panel>
      </div>

      <Panel title="Correlation Matrix">
        {live ? (
          <Table
            head={["A", "B", "ρ"]}
            rows={data!.correlation.map((c) => [c.a, c.b, fmt.num(c.rho, 2)])}
          />
        ) : (
          <EmptyLive note={NOTE} />
        )}
      </Panel>
    </div>
  );
}
