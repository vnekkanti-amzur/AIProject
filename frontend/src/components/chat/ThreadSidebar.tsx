import type { Thread } from '../../types';

interface ThreadSidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function ThreadSidebar({ threads, activeThreadId, onSelect, onNew }: ThreadSidebarProps) {
  return (
    <aside className="w-64 border-r border-slate-200 dark:border-slate-800 flex flex-col">
      <button
        onClick={onNew}
        className="m-3 rounded-md bg-blue-600 hover:bg-blue-700 text-white px-3 py-2"
      >
        New chat
      </button>
      <ul className="flex-1 overflow-y-auto">
        {threads.map((t) => (
          <li key={t.id}>
            <button
              onClick={() => onSelect(t.id)}
              className={
                'w-full text-left px-3 py-2 text-sm truncate ' +
                (t.id === activeThreadId
                  ? 'bg-slate-100 dark:bg-slate-800'
                  : 'hover:bg-slate-50 dark:hover:bg-slate-900')
              }
            >
              {t.title}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
