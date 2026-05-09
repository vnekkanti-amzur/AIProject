export function ImageLoadingSkeleton() {
  return (
    <div className="my-3 rounded-lg overflow-hidden bg-slate-200 dark:bg-slate-700 inline-block">
      <div className="w-80 h-64 bg-gradient-to-r from-slate-300 to-slate-400 dark:from-slate-600 dark:to-slate-700 animate-pulse flex items-center justify-center">
        <div className="text-center">
          <svg
            className="w-12 h-12 text-slate-500 dark:text-slate-400 animate-spin mx-auto mb-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          <p className="text-sm text-slate-600 dark:text-slate-300">Generating image...</p>
        </div>
      </div>
    </div>
  );
}
