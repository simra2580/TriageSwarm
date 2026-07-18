function ResultCard({ title, items, confidence, readyStamp }) {
  const confidenceWidth = `${Math.max(0, Math.min(100, confidence))}%`;

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-blue-950/20 backdrop-blur-xl sm:p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-blue-200/80">Recommendation</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">{title}</h2>
        </div>
        {readyStamp ? (
          <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-200 success-pop">
            Ready
          </span>
        ) : null}
      </div>

      <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/35 p-4">
        <div className="flex items-center justify-between text-xs uppercase tracking-[0.25em] text-slate-400">
          <span>Confidence</span>
          <span>{confidence}%</span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-white/10">
          <div className="confidence-bar h-full rounded-full bg-gradient-to-r from-emerald-300 via-cyan-300 to-blue-400" style={{ width: confidenceWidth }} />
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {items.map((item) => (
          <div key={item.label} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
            <div className={`mb-3 h-1.5 w-24 rounded-full bg-gradient-to-r ${item.accent}`} />
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">{item.label}</p>
            <p className="mt-2 text-sm leading-6 text-slate-100">{item.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default ResultCard;
