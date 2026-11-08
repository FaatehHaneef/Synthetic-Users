import { useEffect, useRef, useState } from 'react';
import { ThinkingOrb } from 'thinking-orbs';
import { api, type Failure, type LiveJob, type SavedRun } from './api';
import InspectScreen from './Inspect';
import LandingOrb from './LandingOrb';
import { GameRows, HomeButton, Notice, SimulatedBadge } from './shared';

type Screen = 'landing' | 'setup' | 'working' | 'output' | 'inspect';
type Source = 'live' | 'saved';
type Result = { type: 'live'; job: LiveJob } | { type: 'saved'; data: SavedRun } | { type: 'failed'; failure: Failure };

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const EXTRA_WORKING_MS = 2000;

function Landing({ onStart }: { onStart: () => void }) {
  return (
    <div className="screen flex min-h-dvh flex-col items-center justify-center">
      <p className="display absolute top-7 left-8 m-0 text-xl font-medium tracking-wide">Synthetic Users</p>
      <LandingOrb />
      <button type="button" className="btn glass -mt-2" onClick={onStart}>
        Get started
      </button>
    </div>
  );
}

function Setup({ onConfirm }: { onConfirm: (source: Source, count: number) => void }) {
  const [source, setSource] = useState<Source>('live');
  const [count, setCount] = useState(1);
  return (
    <form
      className="screen flex min-h-dvh items-center justify-center px-4"
      onSubmit={(event) => {
        event.preventDefault();
        onConfirm(source, count);
      }}
    >
      <div className="flex w-full max-w-sm flex-col gap-6">
        <label className="flex flex-col gap-2 text-neutral-300">
          Source
          <select className="field" value={source} onChange={(event) => setSource(event.target.value as Source)}>
            <option value="live">Live (Gemini)</option>
            <option value="saved">Saved Run</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-neutral-300">
          Participants
          {source === 'saved' ? (
            <select className="field" disabled value="356">
              <option value="356">356</option>
            </select>
          ) : (
            <select className="field" value={count} onChange={(event) => setCount(Number(event.target.value))}>
              {[1, 5, 10].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          )}
        </label>
        <button type="submit" className="btn self-center">
          Confirm
        </button>
      </div>
    </form>
  );
}

function Working({ label, counter }: { label: string; counter: string }) {
  return (
    <div className="screen flex min-h-dvh flex-col items-center justify-center gap-4" role="status" aria-live="polite">
      <div className="card flex items-center gap-4 !rounded-full py-3 pr-8 pl-4">
        <ThinkingOrb state="working" size={64} theme="dark" aria-hidden="true" />
        <span className="text-2xl text-neutral-300">{label}</span>
      </div>
      <p className="m-0 h-6 text-neutral-400 tabular-nums">{counter}</p>
    </div>
  );
}

function LiveOutput({ job }: { job: LiveJob }) {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      {job.summary && job.total > 1 && (
        <h1 className="glow-text m-0 text-center text-4xl font-medium">
          {job.summary.count} of {job.summary.total} named {job.summary.game}
        </h1>
      )}
      <div className={job.items.length > 1 ? 'grid gap-5 md:grid-cols-2' : 'mx-auto max-w-2xl'}>
        {job.items.map((item, index) => (
          <article key={index} className="card p-6">
            <h2 className="glow-text m-0 mb-3 text-2xl font-medium">{item.game}</h2>
            <p className="m-0 text-[1.05rem] leading-relaxed text-neutral-200">{item.answer}</p>
            {item.tags.length > 0 && (
              <p className="m-0 mt-4 flex flex-wrap gap-2 text-sm text-neutral-300">
                {item.tags.map((tag) => (
                  <span key={tag} className="rounded-full border border-white/20 px-3 py-0.5">
                    {tag}
                  </span>
                ))}
              </p>
            )}
          </article>
        ))}
      </div>
      {job.error && <Notice message={job.error.message} />}
    </div>
  );
}

function SavedOutput({ data }: { data: SavedRun }) {
  const [group, setGroup] = useState<'default' | 'persona'>('default');
  const shown = data.groups[group];
  return (
    <div className={`mx-auto flex flex-col items-center ${group === 'persona' ? 'max-w-5xl gap-5' : 'max-w-3xl gap-8'}`}>
      <div className="flex gap-2" role="group" aria-label="Prompt group">
        {(['default', 'persona'] as const).map((value) => (
          <button key={value} type="button" className={`btn ${group === value ? '!border-white !bg-white !text-black' : ''}`} aria-pressed={group === value} onClick={() => setGroup(value)}>
            {value === 'default' ? 'Plain' : 'Persona'}
          </button>
        ))}
      </div>
      <div className="text-center">
        <p className="glow-text m-0 text-8xl font-medium tabular-nums">{shown.share}%</p>
        <h1 className="m-0 mt-2 text-3xl font-normal">named {shown.game}</h1>
        <p className="m-0 mt-3 text-lg text-neutral-300">Real people: {data.human.share}%</p>
      </div>
      <div className="card w-full px-6 py-3">
        {group === 'default' ? (
          <GameRows rows={shown.games} total={shown.total} />
        ) : (
          <ul className="m-0 list-none p-0">
            {data.personas.map((row) => (
              <li key={row.persona} className="flex flex-col justify-between gap-x-6 border-b border-white/8 py-1.5 last:border-0 sm:flex-row sm:items-baseline">
                <span className="text-neutral-300">{row.persona}</span>
                <span className="shrink-0 tabular-nums">
                  {row.game} · {row.count} of {row.total}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Output({ result, onHome, onInspect }: { result: Result; onHome: () => void; onInspect: () => void }) {
  const failed = result.type === 'failed';
  return (
    <div className="screen min-h-dvh px-5 pt-5 pb-20">
      <div className="mb-8 flex items-center justify-between">
        <HomeButton onClick={onHome} />
        {!failed && (
          <button type="button" className="btn" onClick={onInspect}>
            Inspect
          </button>
        )}
      </div>
      {result.type === 'live' && <LiveOutput job={result.job} />}
      {result.type === 'saved' && <SavedOutput data={result.data} />}
      {result.type === 'failed' && <Notice message={result.failure.message} />}
      {!failed && !(result.type === 'live' && result.job.items.length === 0) && <SimulatedBadge />}
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('landing');
  const [working, setWorking] = useState({ label: 'Working....', counter: '' });
  const [result, setResult] = useState<Result | null>(null);
  const mainRef = useRef<HTMLElement>(null);
  const runId = useRef(0);

  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [screen]);

  async function run(source: Source, count: number) {
    const id = ++runId.current;
    setScreen('working');
    setWorking({ label: source === 'saved' ? 'Loading saved run' : 'Working....', counter: source === 'live' && count > 1 ? `0 of ${count}` : '' });
    let next: Result;
    try {
      if (source === 'saved') {
        const data = await api.saved();
        next = { type: 'saved', data };
      } else {
        const { id: jobId } = await api.startLive(count);
        let job = await api.liveStatus(jobId);
        while (job.state === 'running') {
          if (count > 1) setWorking({ label: 'Working....', counter: `${job.done} of ${count}` });
          await delay(600);
          job = await api.liveStatus(jobId);
        }
        next = job.items.length ? { type: 'live', job } : { type: 'failed', failure: job.error ?? { kind: 'other', message: "The request didn't go through. Try again." } };
      }
    } catch (failure) {
      next = { type: 'failed', failure: failure as Failure };
    }
    await delay(EXTRA_WORKING_MS);
    if (id !== runId.current) return;
    setResult(next);
    setScreen('output');
  }

  return (
    <main ref={mainRef} tabIndex={-1} className="outline-none">
      {screen === 'landing' && <Landing onStart={() => setScreen('setup')} />}
      {screen === 'setup' && <Setup onConfirm={run} />}
      {screen === 'working' && <Working {...working} />}
      {screen === 'output' && result && <Output result={result} onHome={() => setScreen('landing')} onInspect={() => setScreen('inspect')} />}
      {screen === 'inspect' && <InspectScreen onHome={() => setScreen('landing')} onBack={result ? () => setScreen('output') : undefined} />}
    </main>
  );
}
