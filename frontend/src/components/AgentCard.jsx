const toneStyles = {
  amber: 'from-amber-400/20 to-orange-500/10 border-amber-300/20 text-amber-100',
  violet: 'from-violet-400/20 to-fuchsia-500/10 border-violet-300/20 text-violet-100',
  cyan: 'from-cyan-400/20 to-blue-500/10 border-cyan-300/20 text-cyan-100',
  slate: 'from-slate-400/10 to-slate-500/5 border-white/10 text-slate-100',
};

function AgentCard({ agent }) {
  const isThinking = agent.status === 'Thinking';

  return (
    <article
      className={`rounded-2xl border bg-gradient-to-br p-4 shadow-lg shadow-black/10 backdrop-blur-md transition-all duration-300 ${toneStyles[agent.tone] ?? toneStyles.cyan} ${isThinking ? 'scale-[1.01] shadow-cyan-950/20' : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{agent.name}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-300">{agent.role}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="rounded-full border border-white/10 bg-slate-950/40 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-slate-200">
            {agent.status}
          </span>
          <span className="text-[11px] uppercase tracking-[0.25em] text-slate-400">{agent.timestamp}</span>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-slate-400">
        {isThinking ? <span className="thinking-dots" aria-hidden="true"><span /><span /><span /></span> : <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_0_4px_rgba(52,211,153,0.12)]" />}
        <span>{isThinking ? 'Thinking' : 'Ready'}</span>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-200">{agent.summary}</p>
      <p className="mt-2 text-sm leading-6 text-slate-400">{agent.details}</p>

      <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-400">
        <span>{Math.round((agent.confidence ?? 0) * 100)}% confidence</span>
        <span>{agent.progress}% complete</span>
      </div>

      <div className="mt-3 h-2 rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-blue-400 to-violet-400 transition-all duration-500 ease-out"
          style={{ width: `${agent.progress}%` }}
        />
      </div>
    </article>
  );
}

export default AgentCard;
