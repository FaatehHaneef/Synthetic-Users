export type Failure = { kind: string; message: string };
export type LiveItem = { game: string; answer: string; words: number; tags: string[] };
export type LiveJob = {
  state: 'running' | 'done';
  done: number;
  total: number;
  items: LiveItem[];
  summary: { game: string; count: number; total: number } | null;
  error: Failure | null;
};
export type Game = { title: string; count: number };
export type PersonaRow = { persona: string; game: string; count: number; total: number; others: Game[] };
export type SavedRun = {
  groups: Record<string, { share: number; game: string; total: number; distinct: number; games: Game[] }>;
  personas: PersonaRow[];
  human: { share: number; distinct: number; total: number };
};
export type ReviewRow = {
  id: string;
  condition: string;
  persona: string;
  title: string;
  answer: string;
  real_game: string;
  gameplay_accurate: string;
  notes: string;
};
export type Tally = { total: number; checked: number; inaccurate: number; unsure: number; not_real_game: number };
export type Inspect = {
  model: string;
  requests: number;
  isFake: boolean;
  comparison: Array<{ group: string; source: string; mentions: number; distinct: number; per100: number; topGame: string; top1: number; top3: number; low?: number; high?: number }>;
  charts: Array<{ id: string; title: string; unit: string; rows: Array<{ label: string; value: number; ours: boolean }> }>;
  games: Record<string, { name: string; rows: Game[] }>;
  personas: PersonaRow[];
  lengths: Array<{ group: string; words: number }>;
  themes: Record<string, { name: string; rows: Array<{ theme: string; count: number }> }>;
  prompt: { interview: string; system: string; personas: string[] };
  review: { rows: ReviewRow[]; tally: Tally };
  titles: Array<{ key: string; title: string; count: number }>;
  aliases: Array<{ from: string; to: string }>;
};

const UNREACHABLE: Failure = { kind: 'other', message: "The request didn't go through. Try again." };

async function call<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch {
    throw UNREACHABLE;
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw (data?.error as Failure) ?? UNREACHABLE;
  return data as T;
}

export const api = {
  startLive: (count: number) => call<{ id: string }>('/api/live', { count }),
  liveStatus: (id: string) => call<LiveJob>(`/api/live/${id}`),
  saved: () => call<SavedRun>('/api/saved'),
  inspect: () => call<Inspect>('/api/inspect'),
  saveReview: (rows: ReviewRow[]) => call<{ tally: Tally }>('/api/review', { rows }),
  merge: (keys: string[], target: string) => call<Inspect>('/api/titles/merge', { keys, target }),
  ignore: (keys: string[]) => call<Inspect>('/api/titles/ignore', { keys }),
  undo: (key: string) => call<Inspect>('/api/titles/undo', { key }),
  exportResults: () => call<{ folder: string; files: string[] }>('/api/export', {}),
};
