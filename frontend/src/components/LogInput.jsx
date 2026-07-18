function LogInput({ value, onChange, onAnalyze, loading, presets, selectedPreset, onSelectPreset }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl sm:p-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/80">Incident log</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Feed the swarm a failure report</h2>
          </div>
          <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-200">
            Connected to backend
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                selectedPreset === preset.label
                  ? 'border-cyan-400/50 bg-cyan-400/15 text-cyan-100'
                  : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10'
              }`}
              onClick={() => onSelectPreset(preset)}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <textarea
          className="min-h-56 w-full rounded-2xl border border-white/10 bg-slate-950/50 p-4 text-sm leading-6 text-slate-200 outline-none transition placeholder:text-slate-500 focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/20"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-white/10 px-3 py-1">Single page dashboard</span>
            <span className="rounded-full border border-white/10 px-3 py-1">Streaming agent updates</span>
            <span className="rounded-full border border-white/10 px-3 py-1">Historical incident memory</span>
          </div>
          <button
            className="rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-500/30 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
            onClick={onAnalyze}
            disabled={loading}
          >
            {loading ? 'Analyzing...' : 'Analyze Incident'}
          </button>
        </div>
      </div>
    </section>
  );
}

export default LogInput;
