"use client";

import { useState } from "react";
import { runEvals, EvalResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FlaskConical, CheckCircle2, XCircle, Loader2 } from "lucide-react";

export default function EvalsPage() {
  const [result, setResult] = useState<EvalResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data = await runEvals();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setRunning(false);
    }
  }

  const pctColor =
    !result ? "" :
    result.percentage === 100 ? "text-green-400" :
    result.percentage >= 70 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="flex flex-col h-full p-6 gap-6 max-w-3xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-lg font-semibold">Eval Suite</h1>
            <p className="text-xs text-muted-foreground">33 tests — structure, guardrails, scope, quality</p>
          </div>
        </div>
        <Button onClick={handleRun} disabled={running} size="sm" className="gap-2">
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
          {running ? "Running…" : "Run Evals"}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Running state */}
      {running && (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm">Running 33 tests against the live API…</p>
          <p className="text-xs">This takes ~2 minutes (LLM judge included)</p>
        </div>
      )}

      {/* Results */}
      {result && !running && (
        <div className="flex flex-col gap-4">
          {/* Summary bar */}
          <div className="flex items-center gap-4 rounded-lg border bg-card px-5 py-4">
            <span className={`text-4xl font-bold tabular-nums ${pctColor}`}>
              {result.percentage}%
            </span>
            <div className="flex flex-col">
              <span className="text-sm font-medium">
                {result.passed}/{result.total} passed
              </span>
              <span className="text-xs text-muted-foreground">
                completed in {result.duration.toFixed(1)}s
              </span>
            </div>
            <div className="ml-auto">
              <Badge variant={result.percentage === 100 ? "default" : "destructive"}>
                {result.percentage === 100 ? "All passing" : `${result.total - result.passed} failing`}
              </Badge>
            </div>
          </div>

          {/* Progress bar */}
          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${result.percentage === 100 ? "bg-green-500" : "bg-yellow-500"}`}
              style={{ width: `${result.percentage}%` }}
            />
          </div>

          {/* Test list */}
          <ScrollArea className="h-[420px] rounded-md border bg-card">
            <div className="divide-y divide-border">
              {result.tests.map((t, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                  {t.status === "PASSED" ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-green-400" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-red-400" />
                  )}
                  <span className="text-sm font-mono text-foreground/80 truncate">{t.name}</span>
                  <Badge
                    variant={t.status === "PASSED" ? "outline" : "destructive"}
                    className="ml-auto shrink-0 text-xs"
                  >
                    {t.status}
                  </Badge>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Empty state */}
      {!result && !running && !error && (
        <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
          <FlaskConical className="h-10 w-10 opacity-30" />
          <p className="text-sm">Click Run Evals to start the test suite</p>
        </div>
      )}
    </div>
  );
}
