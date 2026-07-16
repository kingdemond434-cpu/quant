"use client";

import { usePoll } from "@/lib/api";
import type { MonitoringDashboard } from "@/lib/types";
import { Badge, Table } from "@/components/ui";
import { Panel, StatCard } from "@/components/widgets";
import { fmt } from "@/lib/utils";

export default function MonitoringPage() {
  const { data, updatedAt } = usePoll<MonitoringDashboard>("/api/monitoring", 5000);

  const sevTone = (s: string) =>
    s === "critical" || s === "error" ? "neg" : s === "warning" ? "warn" : "muted";

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Monitoring</h1>
        <span className="num text-[11px] text-muted">
          {updatedAt ? updatedAt.toLocaleTimeString() : "—"}
        </span>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard
          label="Database"
          value={data?.db_present ? "ONLINE" : "MISSING"}
          tone={data?.db_present ? "pos" : "neg"}
        />
        <StatCard label="Schema Version" value={data ? `v${data.schema_version}` : "—"} />
        <StatCard
          label="Audit Chain"
          value={data?.audit_chain_ok ? "OK" : "—"}
          tone={data?.audit_chain_ok ? "pos" : "warn"}
          sub={data ? `${fmt.int(data.audit_entries)} entries` : ""}
        />
        <StatCard
          label="Last Campaign"
          value={data?.last_campaign ? data.last_campaign.slice(0, 10) + "…" : "—"}
        />
      </div>

      <Panel title="Alerts" right={<Badge tone="muted">recent</Badge>}>
        <Table
          head={["Time", "Severity", "Message"]}
          rows={(data?.alerts ?? []).map((a) => [
            a.ts,
            <Badge key={a.ts + a.severity} tone={sevTone(a.severity)}>{a.severity}</Badge>,
            a.message,
          ])}
        />
      </Panel>
    </div>
  );
}
