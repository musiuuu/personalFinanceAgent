import { useCallback, useState } from "react";
import { api, IngestResult } from "../api/client";
import { pkr } from "../format";

interface Props {
  onIngested: () => void;
}

interface UploadState {
  filename: string;
  status: "uploading" | "done" | "error";
  result?: IngestResult;
  error?: string;
}

export default function UploadDropzone({ onIngested }: Props) {
  const [drag, setDrag] = useState(false);
  const [uploads, setUploads] = useState<UploadState[]>([]);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files) return;
      for (const file of Array.from(files)) {
        setUploads((u) => [...u, { filename: file.name, status: "uploading" }]);
        try {
          const result = await api.upload(file);
          setUploads((u) =>
            u.map((x) =>
              x.filename === file.name ? { ...x, status: "done", result } : x,
            ),
          );
          onIngested();
        } catch (e) {
          setUploads((u) =>
            u.map((x) =>
              x.filename === file.name
                ? { ...x, status: "error", error: String(e) }
                : x,
            ),
          );
        }
      }
    },
    [onIngested],
  );

  return (
    <div className="card">
      <div className="card-title">Upload statement</div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${
          drag
            ? "border-emerald-400 bg-emerald-400/10"
            : "border-zinc-700 hover:border-zinc-500"
        }`}
      >
        <span className="text-3xl">📄</span>
        <span className="mt-2 text-sm text-zinc-300">
          Drop a bank statement (.csv / .pdf)
        </span>
        <span className="mt-1 text-xs text-zinc-500">
          or click to browse — every statement is reconciled against its
          printed closing balance
        </span>
        <input
          type="file"
          accept=".csv,.pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>

      {uploads.length > 0 && (
        <ul className="mt-3 space-y-2 text-sm">
          {uploads.slice(-4).map((u, i) => (
            <li
              key={`${u.filename}-${i}`}
              className="flex items-center justify-between rounded-lg bg-zinc-800/60 px-3 py-2"
            >
              <span className="truncate text-zinc-300">{u.filename}</span>
              {u.status === "uploading" && (
                <span className="text-zinc-400">parsing…</span>
              )}
              {u.status === "error" && (
                <span className="text-rose-400">{u.error}</span>
              )}
              {u.status === "done" && u.result && (
                <ResultBadge result={u.result} />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ResultBadge({ result }: { result: IngestResult }) {
  if (result.status === "failed")
    return (
      <span className="font-medium text-rose-400">
        ✗ off by {pkr(Math.abs(result.discrepancy_minor ?? 0))}
      </span>
    );
  const dupes =
    result.skipped_duplicates > 0 ? `, ${result.skipped_duplicates} dupes skipped` : "";
  if (result.reconciled)
    return (
      <span className="font-medium text-emerald-400">
        ✓ reconciled · {result.txn_count} txns{dupes}
      </span>
    );
  return (
    <span className="text-amber-300">
      parsed · {result.txn_count} txns{dupes}
    </span>
  );
}
