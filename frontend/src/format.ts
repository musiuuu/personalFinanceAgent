// The ONLY place minor units become PKR.

export function pkr(minor: number, opts: { sign?: boolean } = {}): string {
  const value = minor / 100;
  const formatted = `PKR ${Math.abs(value).toLocaleString("en-PK", {
    maximumFractionDigits: 0,
  })}`;
  if (opts.sign) return `${value < 0 ? "−" : "+"}${formatted}`;
  return value < 0 ? `−${formatted}` : formatted;
}

export function monthLabel(m: { year: number; month: number }): string {
  return new Date(m.year, m.month - 1, 1).toLocaleString("en", {
    month: "short",
    year: "2-digit",
  });
}

export function monthKey(m: { year: number; month: number }): string {
  return `${m.year}-${String(m.month).padStart(2, "0")}`;
}

export const CATEGORY_COLORS: Record<string, string> = {
  RENT: "#f97316",
  GROCERIES: "#22c55e",
  DINING: "#eab308",
  TRANSPORT: "#06b6d4",
  FUEL: "#a855f7",
  UTILITIES: "#3b82f6",
  SUBSCRIPTIONS: "#ec4899",
  SHOPPING: "#f43f5e",
  HEALTH: "#14b8a6",
  EDUCATION: "#8b5cf6",
  TRAVEL: "#0ea5e9",
  ENTERTAINMENT: "#d946ef",
  FEES_CHARGES: "#64748b",
  CASH_WITHDRAWAL: "#94a3b8",
  TRANSFER_OUT: "#78716c",
  OTHER: "#71717a",
};

export function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? "#71717a";
}
