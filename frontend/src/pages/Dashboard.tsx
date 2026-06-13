import { useCallback, useEffect, useState } from "react";
import {
  Anomaly,
  api,
  Goal,
  MonthCashflow,
  RecurringGroup,
  Summary,
} from "../api/client";
import { pkr } from "../format";
import AnomalyFeed from "../components/AnomalyFeed";
import CashflowChart from "../components/CashflowChart";
import CategoryBreakdown from "../components/CategoryBreakdown";
import ChatPanel from "../components/ChatPanel";
import GoalTracker from "../components/GoalTracker";
import RecurringList from "../components/RecurringList";
import UploadDropzone from "../components/UploadDropzone";

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [months, setMonths] = useState<MonthCashflow[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [recurring, setRecurring] = useState<RecurringGroup[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([
      api.summary(),
      api.cashflow(6),
      api.anomalies(),
      api.recurring(),
      api.goals(),
    ])
      .then(([s, c, a, r, g]) => {
        setSummary(s);
        setMonths(c.months);
        setAnomalies(a.anomalies);
        setRecurring(r.recurring);
        setGoals(g.goals);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(refresh, [refresh]);

  const hasData = (summary?.txn_count ?? 0) > 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Finance<span className="text-emerald-400">Agent</span>
          </h1>
          <p className="mt-0.5 text-sm text-zinc-500">
            LLM plans · deterministic engine computes · every statement reconciled
          </p>
        </div>
        {summary && hasData && (
          <div className="text-right">
            <div className="text-xs uppercase tracking-wider text-zinc-500">
              Balance · as of {summary.as_of}
            </div>
            <div className="text-3xl font-bold tabular-nums text-emerald-400">
              {pkr(summary.current_balance_minor)}
            </div>
            <div className="text-xs text-zinc-500">
              {summary.txn_count} transactions ingested
            </div>
          </div>
        )}
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          Backend unreachable — start it with{" "}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5">
            uvicorn app.main:app
          </code>{" "}
          in <code className="rounded bg-zinc-800 px-1.5 py-0.5">backend/</code>.
        </div>
      )}

      {summary && summary.warnings.length > 0 && (
        <div className="mb-4 rounded-xl border border-amber-700 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
          {summary.warnings.map((w, i) => (
            <p key={i}>⚠ {w}</p>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <UploadDropzone onIngested={refresh} />
            <GoalTracker goals={goals} onChanged={refresh} />
          </div>
          {hasData && <CashflowChart months={months} />}
          {hasData && <CategoryBreakdown months={months} />}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <RecurringList groups={recurring} />
            <AnomalyFeed anomalies={anomalies} />
          </div>
        </div>

        <div className="xl:sticky xl:top-6 xl:h-[calc(100vh-3rem)]">
          <ChatPanel onDataChange={refresh} />
        </div>
      </div>
    </div>
  );
}
