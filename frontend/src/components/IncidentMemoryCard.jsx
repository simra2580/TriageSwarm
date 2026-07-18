function IncidentMemoryCard({ incidents }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-fuchsia-950/20 backdrop-blur-xl sm:p-6">
      <p className="text-xs uppercase tracking-[0.3em] text-fuchsia-200/80">Incident memory</p>
      <h2 className="mt-2 text-2xl font-semibold text-white">Similar failures from local memory</h2>

      <div className="mt-6 space-y-4">
        {incidents.map((incident) => (
          <article key={incident.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-500">{incident.id}</p>
                  <h3 className="mt-1 text-base font-semibold text-white">{incident.title}</h3>
                </div>
                {incident.warning ? (
                  <span className="rounded-full border border-red-400/30 bg-red-400/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-red-200">
                    Recurring
                  </span>
                ) : null}
              </div>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">{incident.date}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{incident.summary}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {incident.tags.map((tag) => (
                <span key={tag} className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
                  {tag}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default IncidentMemoryCard;
