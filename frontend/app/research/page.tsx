"use client";

import { usePoll } from "@/lib/api";
import type { ResearchDashboard } from "@/lib/types";
import { Badge, Table } from "@/components/ui";
import { FunnelBars, Heatmap, HistChart, Panel } from "@/components/widgets";
import { fmt } from "@/lib/utils";

export default function ResearchPage() {
  const { data, updatedAt } = usePoll<ResearchDashboard>("/api/research", 5000);

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Research</h1>
          <p className="text-xs text-muted">
            {data ? `${fmt.int(data.total_tested)} tested · ${data.survivors} survivors` : "…"}
          </p>
        </div>
        <span className="num text-[11px] text-muted">
          {updatedAt ? updatedAt.toLocaleTimeString() : "—"}
        </span>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Discovery Funnel">
          <FunnelBars data={data?.funnel ?? []} />
        </Panel>
        <Panel title="Rejection Analytics" right={<Badge tone="neg">gates</Badge>}>
          <Table
            head={["Gate", "Rejected"]}
            rows={(data?.rejections ?? []).map((r) => [r.gate, fmt.int(r.count)])}
          />
        </Panel>
        <Panel title="DSR Distribution">
          <HistChart data={data?.dsr_distribution ?? []} color="#22d3ee" />
        </Panel>
        <Panel title="PBO Distribution">
          <HistChart data={data?.pbo_distribution ?? []} color="#fbbf24" />
        </Panel>
      </div>

      <Panel title="Family Rankings">
        <Table
          head={["Family", "Tested", "Survivors", "Survivor rate", "Avg DSR"]}
          rows={(data?.families ?? []).map((f) => [
            <span key={f.family} className="capitalize">{f.family}</span>,
            fmt.int(f.tested),
            fmt.int(f.survivors),
            fmt.pct(f.survivor_rate),
            fmt.num(f.avg_dsr, 3),
          ])}
        />
      </Panel>

      <Panel title="Candidate Heatmap" right={<span className="text-[10px] text-muted">best DSR</span>}>
        <Heatmap cells={data?.heatmap ?? []} />
      </Panel>
    </div>
  );
}
