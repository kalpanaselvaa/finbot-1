const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface EvalCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface EvalCheckResult {
  checks: EvalCheck[];
  passed: number;
  total: number;
  percentage: number;
}

export async function checkEval(query: string, text: string): Promise<EvalCheckResult> {
  const res = await fetch(`${API_URL}/evals/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, text }),
  });
  if (!res.ok) throw new Error(`Check API error ${res.status}`);
  return res.json() as Promise<EvalCheckResult>;
}

export interface EvalTest {
  name: string;
  status: "PASSED" | "FAILED";
}

export interface EvalResult {
  tests: EvalTest[];
  passed: number;
  total: number;
  percentage: number;
  duration: number;
  raw: string;
}

export async function runEvals(): Promise<EvalResult> {
  const res = await fetch(`${API_URL}/evals/run`, { method: "POST" });
  if (!res.ok) throw new Error(`Evals API error ${res.status}`);
  return res.json() as Promise<EvalResult>;
}

export async function fetchBrief(query: string, thread_id: string): Promise<string> {
  const res = await fetch(`${API_URL}/brief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, thread_id }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  const data = (await res.json()) as { result: string };
  return data.result;
}
