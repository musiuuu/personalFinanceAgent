import { useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ChatResponse } from "../api/client";
import { pkr } from "../format";

interface Message {
  role: "user" | "agent";
  text: string;
  response?: ChatResponse;
}

const SUGGESTIONS = [
  "Can I afford a 250,000 PKR laptop next month?",
  "Where am I overspending?",
  "Create a 3-month savings plan for 300,000",
  "What if I cancel Netflix and cut dining by 30%?",
];

export default function ChatPanel({ onDataChange }: { onDataChange: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, busy]);

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const response = await api.chat(text);
      setMessages((m) => [...m, { role: "agent", text: response.answer, response }]);
      onDataChange();
    } catch (e) {
      setMessages((m) => [...m, { role: "agent", text: `Something went wrong: ${e}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card flex h-full min-h-[480px] flex-col">
      <div className="card-title">Ask the agent</div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-zinc-500">
              The LLM routes your question to a deterministic engine — every
              number is computed, never guessed. Try:
            </p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="block w-full rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-left text-xs text-zinc-300 hover:border-zinc-600"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div
              className={`max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-emerald-600/90 text-white"
                  : "bg-zinc-800/80 text-zinc-100"
              }`}
            >
              <div className="whitespace-pre-wrap">{m.text}</div>
              {m.response && <StructuredData response={m.response} />}
              {m.response && m.response.tool_calls.length > 0 && (
                <div className="mt-2 text-[10px] uppercase tracking-wide text-zinc-500">
                  {m.response.intent} · {m.response.tool_calls[0].name} ·{" "}
                  {m.response.explained_by}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="text-sm text-zinc-500">thinking…</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-3 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your money…"
          className="flex-1 rounded-xl border border-zinc-700 bg-zinc-800 px-3.5 py-2.5 text-sm outline-none placeholder:text-zinc-500 focus:border-emerald-500"
        />
        <button
          disabled={busy || !input.trim()}
          className="rounded-xl bg-emerald-600 px-4 text-sm font-semibold disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}

// Renders the structured tool payload under the prose as a chart/table.
function StructuredData({ response }: { response: ChatResponse }) {
  const tool = response.tool_calls[0]?.name;
  const r = response.data?.result;
  if (!r) return null;

  if (tool === "savings_plan_tool" && Array.isArray(r.schedule)) {
    const data = r.schedule.map((m: any) => ({
      name: `M${m.month_index}`,
      saved: m.cumulative_saved_minor / 100,
    }));
    return (
      <ChartShell>
        <BarChart data={data}>
          <XAxis dataKey="name" stroke="#71717a" fontSize={10} tickLine={false} />
          <YAxis hide />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => [pkr(Math.round(v * 100)), "saved"]}
          />
          <Bar dataKey="saved" fill="#34d399" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ChartShell>
    );
  }

  if (tool === "simulate_tool" && Array.isArray(r.months)) {
    const data = r.months.map((m: any) => ({
      name: `M${m.month_index}`,
      baseline: m.balance_before_minor / 100,
      scenario: m.balance_after_minor / 100,
    }));
    return (
      <ChartShell>
        <LineChart data={data}>
          <XAxis dataKey="name" stroke="#71717a" fontSize={10} tickLine={false} />
          <YAxis hide />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number, n: string) => [pkr(Math.round(v * 100)), n]}
          />
          <Line dataKey="baseline" stroke="#71717a" strokeWidth={2} dot={false} />
          <Line dataKey="scenario" stroke="#34d399" strokeWidth={2} dot={false} />
        </LineChart>
      </ChartShell>
    );
  }

  if (tool === "affordability_tool" && typeof r.affordable === "boolean") {
    const rows: [string, number][] = [
      ["Current balance", r.current_balance_minor],
      ["Expected income", r.expected_income_total_minor],
      ["Recurring bills", -r.expected_recurring_total_minor],
      ["Variable spend", -r.expected_variable_total_minor],
      ["Purchase", -r.purchase_minor],
      ["Left after purchase", r.balance_after_purchase_minor],
    ];
    return (
      <div className="mt-2 overflow-hidden rounded-xl border border-zinc-700/60 text-xs">
        {rows.map(([label, v]) => (
          <div
            key={label}
            className="flex justify-between border-b border-zinc-700/40 bg-zinc-900/60 px-2.5 py-1.5 last:border-0"
          >
            <span className="text-zinc-400">{label}</span>
            <span
              className={`tabular-nums ${v < 0 ? "text-rose-300" : "text-emerald-300"}`}
            >
              {pkr(v, { sign: true })}
            </span>
          </div>
        ))}
      </div>
    );
  }

  if (tool === "sql_tool" && Array.isArray(r.rows) && r.rows.length > 0) {
    return (
      <div className="mt-2 max-h-44 overflow-auto rounded-xl border border-zinc-700/60 text-xs">
        <table className="w-full">
          <thead className="bg-zinc-900 text-left text-zinc-400">
            <tr>
              {r.columns.map((c: string) => (
                <th key={c} className="px-2 py-1 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {r.rows.slice(0, 20).map((row: any[], i: number) => (
              <tr key={i} className="border-t border-zinc-800">
                {row.map((v, j) => (
                  <td key={j} className="px-2 py-1 tabular-nums text-zinc-300">
                    {String(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return null;
}

const tooltipStyle = {
  background: "#18181b",
  border: "1px solid #3f3f46",
  borderRadius: 10,
  fontSize: 12,
};

function ChartShell({ children }: { children: React.ReactElement }) {
  return (
    <div className="mt-2 rounded-xl border border-zinc-700/60 bg-zinc-900/60 p-2">
      <ResponsiveContainer width="100%" height={130}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}
