import { RecurringGroup } from "../api/client";
import { pkr } from "../format";

function cadenceLabel(days: number): string {
  if (days === 7) return "weekly";
  if (days === 30) return "monthly";
  if (days === 365) return "yearly";
  return `every ${days}d`;
}

export default function RecurringList({ groups }: { groups: RecurringGroup[] }) {
  const outflows = groups.filter((g) => g.typical_amount_minor < 0);
  return (
    <div className="card">
      <div className="card-title">Recurring payments</div>
      {outflows.length === 0 ? (
        <p className="text-sm text-zinc-500">
          No recurring payments detected yet — they need ≥3 occurrences.
        </p>
      ) : (
        <ul className="space-y-2">
          {outflows.map((g) => (
            <li
              key={g.group_id}
              className="flex items-center justify-between rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2.5"
            >
              <div>
                <div className="text-sm font-medium text-zinc-200">{g.merchant}</div>
                <div className="text-xs text-zinc-500">
                  {cadenceLabel(g.cadence_days)} · {g.occurrences}× · ~
                  {pkr(Math.abs(g.monthly_equivalent_minor))}/mo
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm tabular-nums text-zinc-300">
                  {pkr(Math.abs(g.last_amount_minor ?? g.typical_amount_minor))}
                </div>
                {g.price_change && g.price_change_pct !== null && (
                  <div
                    className={`text-[11px] font-semibold ${
                      g.price_change_pct > 0 ? "text-rose-400" : "text-emerald-400"
                    }`}
                  >
                    {g.price_change_pct > 0 ? "▲" : "▼"}{" "}
                    {Math.abs(g.price_change_pct)}% price change
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
