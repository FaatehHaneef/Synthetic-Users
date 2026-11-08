import { Badge, BadgeDot } from '@/components/ui/badge';

export function HomeButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="btn !p-2.5" onClick={onClick} aria-label="Home" title="Home">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 11.5 12 4l9 7.5" />
        <path d="M5.5 9.8V20h13V9.8" />
        <path d="M10 20v-5.5h4V20" />
      </svg>
    </button>
  );
}

export function SimulatedBadge() {
  return (
    <div className="fixed right-5 bottom-5 z-20">
      <Badge variant="primary" appearance="light" shape="circle" size="lg" className="px-3 text-[0.8rem] text-blue-300 dark:text-blue-300">
        <BadgeDot />
        Simulated participants
      </Badge>
    </div>
  );
}

export function Notice({ message }: { message: string }) {
  return (
    <div className="card mx-auto max-w-md px-6 py-5 text-center text-lg" role="alert">
      {message}
    </div>
  );
}

export function GameRows({ rows, total }: { rows: Array<{ title: string; count: number }>; total: number }) {
  return (
    <ul className="m-0 list-none p-0">
      {rows.map((row) => (
        <li key={row.title} className="flex items-baseline justify-between gap-4 border-b border-white/8 py-2.5 last:border-0">
          <span>{row.title}</span>
          <span className="text-neutral-300 tabular-nums">
            {row.count} of {total}
          </span>
        </li>
      ))}
    </ul>
  );
}
