import { useState } from "react";
import { api, Goal } from "../api/client";
import { pkr } from "../format";

interface Props {
  goals: Goal[];
  onChanged: () => void;
}

export default function GoalTracker({ goals, onChanged }: Props) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");

  const submit = async () => {
    const pkrValue = Number(amount.replace(/,/g, ""));
    if (!name || !pkrValue || !date) return;
    await api.createGoal({
      name,
      target_amount_minor: Math.round(pkrValue * 100),
      target_date: date,
    });
    setName("");
    setAmount("");
    setDate("");
    setAdding(false);
    onChanged();
  };

  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <div className="card-title mb-0">Goals</div>
        <button
          onClick={() => setAdding((a) => !a)}
          className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-200 hover:bg-zinc-700"
        >
          {adding ? "Cancel" : "+ Add"}
        </button>
      </div>

      {adding && (
        <div className="mb-4 space-y-2 rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
          <input
            placeholder="Goal name (e.g. Laptop)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm"
          />
          <div className="flex gap-2">
            <input
              placeholder="Amount (PKR)"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-1/2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm"
            />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-1/2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-300"
            />
          </div>
          <button
            onClick={submit}
            className="w-full rounded-lg bg-emerald-600 py-1.5 text-sm font-semibold hover:bg-emerald-500"
          >
            Create goal
          </button>
        </div>
      )}

      {goals.length === 0 && !adding && (
        <p className="text-sm text-zinc-500">
          No goals yet — add one and the engine will project a completion date
          from your forecast surplus.
        </p>
      )}

      <div className="space-y-4">
        {goals.map((g) => {
          const pct = Math.min(
            100,
            Math.round((g.saved_so_far_minor / g.target_amount_minor) * 100),
          );
          return (
            <div key={g.id}>
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="font-medium text-zinc-200">{g.name}</span>
                <span className="text-xs text-zinc-400">
                  {pkr(g.saved_so_far_minor)} / {pkr(g.target_amount_minor)}
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className={`h-full rounded-full ${g.on_track ? "bg-emerald-500" : "bg-amber-500"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="mt-1 flex justify-between text-xs text-zinc-500">
                <span>due {g.target_date}</span>
                {g.projected_completion ? (
                  <span className={g.on_track ? "text-emerald-400" : "text-amber-400"}>
                    projected {g.projected_completion}
                    {g.on_track ? " · on track" : " · behind"}
                  </span>
                ) : (
                  <span className="text-rose-400">no surplus to save from</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
