import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api, MonthCashflow, Txn } from "../api/client";
import { categoryColor, monthKey, monthLabel, pkr } from "../format";

interface Props {
  months: MonthCashflow[];
}

export default function CategoryBreakdown({ months }: Props) {
  const withData = months.filter((m) => m.txn_count > 0);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [txns, setTxns] = useState<Txn[]>([]);

  const current =
    withData.find((m) => monthKey(m.month) === selectedMonth) ??
    withData[withData.length - 1];

  useEffect(() => {
    if (!current || !selectedCategory) {
      setTxns([]);
      return;
    }
    api
      .transactions({ month: monthKey(current.month), category: selectedCategory })
      .then((r) => setTxns(r.transactions))
      .catch(() => setTxns([]));
  }, [selectedCategory, current?.month.year, current?.month.month]);

  if (!current)
    return (
      <div className="card">
        <div className="card-title">Spending by category</div>
        <p className="text-sm text-zinc-500">Upload a statement to see spending.</p>
      </div>
    );

  const slices = Object.entries(current.by_category)
    .sort(([, a], [, b]) => b - a)
    .map(([category, amount]) => ({
      name: category,
      value: amount / 100,
    }));

  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <div className="card-title mb-0">Spending by category</div>
        <select
          className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-200"
          value={monthKey(current.month)}
          onChange={(e) => {
            setSelectedMonth(e.target.value);
            setSelectedCategory(null);
          }}
        >
          {withData.map((m) => (
            <option key={monthKey(m.month)} value={monthKey(m.month)}>
              {monthLabel(m.month)}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row">
        <ResponsiveContainer width="100%" height={210} className="sm:max-w-[220px]">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              innerRadius={55}
              outerRadius={90}
              paddingAngle={2}
              strokeWidth={0}
              isAnimationActive={false}
              onClick={(slice) =>
                setSelectedCategory((c) => (c === slice.name ? null : slice.name))
              }
            >
              {slices.map((s) => (
                <Cell
                  key={s.name}
                  fill={categoryColor(s.name)}
                  opacity={!selectedCategory || selectedCategory === s.name ? 1 : 0.25}
                  cursor="pointer"
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: 12,
                fontSize: 13,
              }}
              formatter={(value: number, name: string) => [
                pkr(Math.round(value * 100)),
                name,
              ]}
            />
          </PieChart>
        </ResponsiveContainer>

        <div className="flex-1 space-y-1.5 text-sm">
          {slices.map((s) => (
            <button
              key={s.name}
              onClick={() =>
                setSelectedCategory((c) => (c === s.name ? null : s.name))
              }
              className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left transition-colors ${
                selectedCategory === s.name ? "bg-zinc-800" : "hover:bg-zinc-800/50"
              }`}
            >
              <span className="flex items-center gap-2 text-zinc-300">
                <span
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ background: categoryColor(s.name) }}
                />
                {s.name}
              </span>
              <span className="tabular-nums text-zinc-400">
                {pkr(Math.round(s.value * 100))}
              </span>
            </button>
          ))}
        </div>
      </div>

      {selectedCategory && txns.length > 0 && (
        <div className="mt-3 max-h-44 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-950/50">
          {txns.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between border-b border-zinc-800/60 px-3 py-2 text-xs last:border-0"
            >
              <span className="text-zinc-500">{t.txn_date}</span>
              <span className="mx-2 flex-1 truncate text-zinc-300">
                {t.merchant ?? t.raw_description}
              </span>
              <span className="tabular-nums text-zinc-200">
                {pkr(t.amount_minor)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
