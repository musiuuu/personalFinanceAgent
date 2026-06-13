import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MonthCashflow } from "../api/client";
import { monthLabel, pkr } from "../format";

export default function CashflowChart({ months }: { months: MonthCashflow[] }) {
  const data = months.map((m) => ({
    name: monthLabel(m.month),
    income: m.income_minor / 100,
    expense: m.expense_minor / 100,
    net: m.net_minor / 100,
  }));

  return (
    <div className="card">
      <div className="card-title">Cashflow — last {months.length} months</div>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} barGap={2}>
          <CartesianGrid stroke="#27272a" vertical={false} />
          <XAxis dataKey="name" stroke="#71717a" fontSize={12} tickLine={false} />
          <YAxis
            stroke="#71717a"
            fontSize={11}
            tickLine={false}
            tickFormatter={(v: number) => `${Math.round(v / 1000)}k`}
            width={42}
          />
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
          <Bar
            dataKey="income"
            fill="#34d399"
            radius={[6, 6, 0, 0]}
            maxBarSize={26}
            isAnimationActive={false}
          />
          <Bar
            dataKey="expense"
            fill="#fb7185"
            radius={[6, 6, 0, 0]}
            maxBarSize={26}
            isAnimationActive={false}
          />
          <Line
            dataKey="net"
            stroke="#a78bfa"
            strokeWidth={2.5}
            dot={{ r: 3, fill: "#a78bfa" }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-1 flex gap-4 text-xs text-zinc-400">
        <Legend color="#34d399" label="Income" />
        <Legend color="#fb7185" label="Expenses" />
        <Legend color="#a78bfa" label="Net" />
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}
