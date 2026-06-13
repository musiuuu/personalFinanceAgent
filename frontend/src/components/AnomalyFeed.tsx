import { Anomaly } from "../api/client";
import { pkr } from "../format";

const KIND_META: Record<string, { label: string; classes: string }> = {
  robust_outlier: { label: "Outlier", classes: "bg-amber-500/15 text-amber-300" },
  new_large_merchant: { label: "New & large", classes: "bg-sky-500/15 text-sky-300" },
  duplicate_charge: { label: "Duplicate", classes: "bg-rose-500/15 text-rose-300" },
  recurring_price_spike: {
    label: "Price change",
    classes: "bg-fuchsia-500/15 text-fuchsia-300",
  },
};

export default function AnomalyFeed({ anomalies }: { anomalies: Anomaly[] }) {
  return (
    <div className="card">
      <div className="card-title">Anomalies</div>
      {anomalies.length === 0 ? (
        <p className="text-sm text-zinc-500">Nothing unusual detected.</p>
      ) : (
        <ul className="max-h-72 space-y-2.5 overflow-y-auto pr-1">
          {anomalies.map((a, i) => {
            const meta = KIND_META[a.kind] ?? {
              label: a.kind,
              classes: "bg-zinc-700 text-zinc-300",
            };
            return (
              <li
                key={`${a.txn_id}-${a.kind}-${i}`}
                className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-3"
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${meta.classes}`}
                  >
                    {meta.label}
                  </span>
                  <span className="text-xs tabular-nums text-zinc-400">
                    {a.txn_date} · {pkr(a.amount_minor)}
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-zinc-300">{a.reason}</p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
