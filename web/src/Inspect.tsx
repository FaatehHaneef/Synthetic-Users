import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, type Failure, type Inspect, type ReviewRow, type Tally } from './api';
import { GameRows, HomeButton, Notice, SimulatedBadge } from './shared';

const SECTIONS = [
  ['comparison', 'Comparison'],
  ['games', 'Games'],
  ['personas', 'Personas'],
  ['length', 'Length and themes'],
  ['prompt', 'Prompt'],
  ['review', 'Review'],
  ['titles', 'Titles'],
  ['export', 'Export'],
] as const;

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="m-0 mb-4 text-2xl font-medium">{title}</h2>
      {children}
    </section>
  );
}

function Bars({ chart }: { chart: Inspect['charts'][number] }) {
  const max = Math.max(...chart.rows.map((row) => row.value), 1);
  return (
    <figure className="card m-0 p-6">
      <figcaption className="mb-5 text-lg">{chart.title}</figcaption>
      <div className="flex flex-col gap-3.5">
        {chart.rows.map((row) => (
          <div key={row.label} className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[16rem_1fr]">
            <span className="text-neutral-300">{row.label}</span>
            <div className="flex items-center gap-3">
              <div className={`h-4 rounded-sm ${row.ours ? 'solid-glow' : 'hatched'}`} style={{ width: `${(row.value / max) * 85}%`, minWidth: 3 }} />
              <span className="font-medium tabular-nums">{row.value}</span>
            </div>
          </div>
        ))}
      </div>
      <p className="m-0 mt-5 text-sm text-neutral-400">{chart.unit}. Hatched: the paper's Table 6 (GPT-3). Solid: our run.</p>
    </figure>
  );
}

const OPTIONS = ['', 'yes', 'no', 'unsure'];

function ReviewCard({ row, onChange }: { row: ReviewRow; onChange: (patch: Partial<ReviewRow>) => void }) {
  return (
    <article className="card flex flex-col gap-4 p-5">
      <div>
        <h3 className="m-0 text-xl font-medium">{row.title}</h3>
        <p className="m-0 mt-1 text-sm text-neutral-400">{row.persona || 'Plain prompt'}</p>
      </div>
      <p className="m-0 leading-relaxed text-neutral-200">{row.answer}</p>
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_2fr]">
        {(
          [
            ['real_game', 'Is the game real?'],
            ['gameplay_accurate', 'Gameplay accurate?'],
          ] as const
        ).map(([field, label]) => (
          <label key={field} className="flex flex-col gap-1.5 text-sm text-neutral-300">
            {label}
            <select className="field" value={row[field]} onChange={(event) => onChange({ [field]: event.target.value })}>
              {OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option || 'Not checked'}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label className="flex flex-col gap-1.5 text-sm text-neutral-300">
          Notes
          <input className="field" value={row.notes} onChange={(event) => onChange({ notes: event.target.value })} />
        </label>
      </div>
    </article>
  );
}

function tallyOf(rows: ReviewRow[]): Tally {
  const checked = rows.filter((row) => row.gameplay_accurate);
  return {
    total: rows.length,
    checked: checked.length,
    inaccurate: checked.filter((row) => row.gameplay_accurate === 'no').length,
    unsure: checked.filter((row) => row.gameplay_accurate === 'unsure').length,
    not_real_game: rows.filter((row) => row.real_game === 'no').length,
  };
}

export default function InspectScreen({ onHome, onBack }: { onHome: () => void; onBack?: () => void }) {
  const [data, setData] = useState<Inspect | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [saveNote, setSaveNote] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);
  const [target, setTarget] = useState('');
  const [exported, setExported] = useState<{ folder: string; files: string[] } | null>(null);

  useEffect(() => {
    api.inspect().then(accept).catch(setFailure);
  }, []);

  function accept(next: Inspect) {
    setData(next);
    setRows((current) => (current.length ? current : next.review.rows));
    setChosen([]);
    setTarget('');
  }

  const tally = useMemo(() => tallyOf(rows), [rows]);
  const act = (promise: Promise<Inspect>) => promise.then(accept).catch(setFailure);

  async function saveReview() {
    try {
      await api.saveReview(rows);
      setSaveNote('Saved.');
    } catch (error) {
      setFailure(error as Failure);
    }
  }

  return (
    <div className="screen min-h-dvh px-5 pt-5 pb-24">
      <div className="mx-auto mb-8 flex max-w-[1800px] items-center justify-between">
        <HomeButton onClick={onHome} />
        {onBack && (
          <button type="button" className="btn" onClick={onBack}>
            Back to results
          </button>
        )}
      </div>

      {failure && !data && <Notice message={failure.message} />}
      {data && (
        <div className="mx-auto flex max-w-[1800px] flex-col gap-14">
          <header>
            <h1 className="glow-text m-0 text-4xl font-medium">Inspect</h1>
            <p className="m-0 mt-2 text-neutral-300">
              {data.model}, {data.requests} requests. Illustrates Hämäläinen et al. (CHI '23), does not reproduce it.
            </p>
            {data.isFake && (
              <p className="m-0 mt-2 font-medium text-red-300" role="alert">
                Fake test data. Do not use these numbers.
              </p>
            )}
            <nav aria-label="Sections" className="mt-5 flex flex-wrap gap-2">
              {SECTIONS.map(([id, label]) => (
                <a key={id} href={`#${id}`} className="btn !px-3.5 !py-1.5 !text-sm no-underline">
                  {label}
                </a>
              ))}
            </nav>
          </header>

          <Section id="comparison" title="Comparison with the paper">
            <div className="card overflow-x-auto p-6">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Group</th>
                    <th scope="col">Mentions</th>
                    <th scope="col">Different games</th>
                    <th scope="col">Per 100</th>
                    <th scope="col">Top game</th>
                    <th scope="col">Top share</th>
                    <th scope="col">Top 3</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {data.comparison.map((row) => (
                    <tr key={row.group}>
                      <td>{row.group}</td>
                      <td>{row.mentions}</td>
                      <td>{row.distinct}</td>
                      <td>{row.per100}</td>
                      <td>{row.topGame}</td>
                      <td>
                        {row.top1}%{row.low !== undefined && <span className="block text-sm text-neutral-400">95%: {row.low} to {row.high}</span>}
                      </td>
                      <td>{row.top3}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="m-0 mt-4 text-sm text-neutral-400">Paper rows are our arithmetic on the authors' Table 6. Our rows are one model on one question.</p>
            </div>
            <div className="mt-5 grid gap-5 xl:grid-cols-2">
              {data.charts.map((chart) => (
                <Bars key={chart.id} chart={chart} />
              ))}
            </div>
          </Section>

          <Section id="games" title="Most mentioned games">
            <div className="grid gap-5 md:grid-cols-2">
              {Object.entries(data.games).map(([key, group]) => (
                <div key={key} className="card px-6 py-4">
                  <h3 className="m-0 mb-2 text-lg font-medium">{group.name}</h3>
                  <GameRows rows={group.rows.slice(0, 12)} total={group.rows.reduce((sum, row) => sum + row.count, 0)} />
                </div>
              ))}
            </div>
          </Section>

          <Section id="personas" title="Top game per persona">
            <div className="card overflow-x-auto p-6">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Persona</th>
                    <th scope="col">Top game</th>
                    <th scope="col">Count</th>
                    <th scope="col">Others</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {data.personas.map((row) => (
                    <tr key={row.persona}>
                      <td>{row.persona}</td>
                      <td>{row.game}</td>
                      <td>
                        {row.count} of {row.total}
                      </td>
                      <td className="text-neutral-300">{row.others.map((other) => `${other.title} (${other.count})`).join(', ') || 'None'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section id="length" title="Length and themes">
            <div className="grid gap-5 md:grid-cols-3">
              <div className="card px-6 py-4">
                <h3 className="m-0 mb-2 text-lg font-medium">Mean words</h3>
                <ul className="m-0 list-none p-0">
                  {data.lengths.map((row) => (
                    <li key={row.group} className="flex justify-between gap-4 border-b border-white/8 py-2.5 last:border-0">
                      <span>{row.group}</span>
                      <span className="tabular-nums">{row.words}</span>
                    </li>
                  ))}
                </ul>
              </div>
              {Object.entries(data.themes).map(([key, group]) => (
                <div key={key} className="card px-6 py-4">
                  <h3 className="m-0 mb-2 text-lg font-medium">Themes: {group.name}</h3>
                  <ul className="m-0 list-none p-0">
                    {group.rows.map((row) => (
                      <li key={row.theme} className="flex justify-between gap-4 border-b border-white/8 py-2 last:border-0">
                        <span>{row.theme}</span>
                        <span className="tabular-nums">{row.count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <p className="m-0 mt-3 text-sm text-neutral-400">Themes are whole-word keyword matches. Answers can have several.</p>
          </Section>

          <Section id="prompt" title="Exact prompt">
            <div className="flex flex-col gap-3">
              {(
                [
                  ['Interview, verbatim from the paper (Table 1)', data.prompt.interview],
                  ['Our addition: instruction for a chat model', data.prompt.system],
                  ['Our addition: persona lines, persona group only', data.prompt.personas.map((p) => `(Participant background: ${p}.)`).join('\n')],
                ] as const
              ).map(([label, text]) => (
                <details key={label} className="card px-5 py-4">
                  <summary className="cursor-pointer">{label}</summary>
                  <pre className="m-0 mt-3 font-mono text-sm leading-relaxed whitespace-pre-wrap text-neutral-200">{text}</pre>
                </details>
              ))}
            </div>
          </Section>

          <Section id="review" title="Hallucination review">
            <p className="glow-text m-0 mb-1 text-xl" aria-live="polite">
              {tally.inaccurate} of {tally.checked} reviewed responses had inaccurate gameplay
            </p>
            <p className="m-0 mb-5 text-neutral-300">
              {tally.unsure} unsure, {tally.not_real_game} named a game that is not real, {tally.total - tally.checked} not reviewed yet. Filled in by a person.
            </p>
            <div className="mb-5 flex items-center gap-4">
              <button type="button" className="btn" onClick={saveReview}>
                Save review
              </button>
              <span>{saveNote}</span>
            </div>
            <div className="grid items-start gap-4 xl:grid-cols-2">
              {rows.map((row) => (
                <ReviewCard
                  key={row.id}
                  row={row}
                  onChange={(patch) => {
                    setSaveNote('');
                    setRows((current) => current.map((item) => (item.id === row.id ? { ...item, ...patch } : item)));
                  }}
                />
              ))}
            </div>
            <div className="mt-5 flex items-center gap-4">
              <button type="button" className="btn" onClick={saveReview}>
                Save review
              </button>
              <span role="status">{saveNote}</span>
            </div>
          </Section>

          <Section id="titles" title="Clean up titles">
            <div className="card flex flex-col gap-5 p-6">
              <fieldset className="m-0 grid gap-x-6 gap-y-1.5 border-0 p-0 sm:grid-cols-2">
                <legend className="mb-2 p-0 text-neutral-300">Select titles that mean the same game</legend>
                {data.titles.map((title) => (
                  <label key={title.key} className="flex cursor-pointer items-center gap-3 py-1">
                    <input
                      type="checkbox"
                      className="size-4 accent-white"
                      checked={chosen.includes(title.key)}
                      onChange={(event) => setChosen((current) => (event.target.checked ? [...current, title.key] : current.filter((key) => key !== title.key)))}
                    />
                    <span>
                      {title.title} <span className="text-neutral-400 tabular-nums">({title.count})</span>
                    </span>
                  </label>
                ))}
              </fieldset>
              <label className="flex max-w-md flex-col gap-1.5 text-sm text-neutral-300">
                Merge into this title
                <input className="field" value={target} onChange={(event) => setTarget(event.target.value)} />
              </label>
              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn" disabled={!chosen.length || !target.trim()} onClick={() => act(api.merge(chosen, target))}>
                  Merge titles
                </button>
                <button type="button" className="btn" disabled={!chosen.length} onClick={() => act(api.ignore(chosen))}>
                  Exclude: not a published game
                </button>
              </div>
              {data.aliases.length > 0 && (
                <div>
                  <h3 className="m-0 mb-2 text-lg font-medium">Current merges</h3>
                  <ul className="m-0 list-none p-0">
                    {data.aliases.map((alias) => (
                      <li key={alias.from} className="flex items-center justify-between gap-4 border-b border-white/8 py-2 last:border-0">
                        <span>
                          {alias.from} → {alias.to === '__ignore__' ? 'excluded' : alias.to}
                        </span>
                        <button type="button" className="btn !px-3 !py-1 !text-sm" onClick={() => act(api.undo(alias.from))}>
                          Undo
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Section>

          <Section id="export" title="Export">
            <div className="card flex flex-col items-start gap-4 p-6">
              <p className="m-0 text-neutral-300">Writes the CSV files, charts and summary for the slides and guide.</p>
              <button type="button" className="btn" onClick={() => api.exportResults().then(setExported).catch(setFailure)}>
                Export results
              </button>
              {exported && (
                <p className="m-0" role="status">
                  Written to {exported.folder}: {exported.files.join(', ')}
                </p>
              )}
            </div>
          </Section>
          {failure && <Notice message={failure.message} />}
        </div>
      )}
      <SimulatedBadge />
    </div>
  );
}
