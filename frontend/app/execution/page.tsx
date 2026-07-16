"use client";

import { usePoll } from "@/lib/api";
import type { ExecutionDashboard } from "@/lib/types";
import { Badge, Table } from "@/components/ui";
import { EmptyLive, Panel, StatCard } from "@/components/widgets";
import { fmt } from "@/lib/utils";

export default function ExecutionPage() {
  const { data } = usePoll<ExecutionDashboard>("/api/execution", 4000);
  const live = data?.live ?? false;

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Execution</h1>
        <Badge tone={data?.mt5_connected ? "pos" : "neg"}>
          MT5 {data?.mt5_connected ? "connected" : "offline"}
        </Badge>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="MT5 Server" value={data?.server || "—"} />
        <StatCard label="Fills" value={data ? fmt.int(data.fills) : "—"} />
        <StatCard
          label="Avg Slippage"
          value={data ? `${fmt.num(data.avg_slippage_bps, 1)} bps` : "—"}
          tone="warn"
        />
        <StatCard
          label="Avg Latency"
          value={data ? `${fmt.num(data.avg_latency_ms, 0)} ms` : "—"}
        />
      </div>

      <Panel title="Orders &amp; Fills">
        {live ? (
          <Table
            head={["Time", "Symbol", "Side", "Qty", "Status"]}
            rows={data!.orders.map((o) => [o.ts, o.symbol, o.side, fmt.num(o.qty, 2), o.status])}
          />
        ) : (
          <EmptyLive note="Execution telemetry (orders, fills, slippage, latency) streams once the MT5 EA bridge is live on a funded demo/real account. Markets closed / no live book at present." />
        )}
      </Panel>
    </div>
  );
}
