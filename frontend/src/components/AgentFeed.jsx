import AgentCard from './AgentCard.jsx';

function AgentFeed({ agents, order }) {
  const orderedAgents = order.map((name) => agents.find((agent) => agent.name === name)).filter(Boolean);

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-violet-950/20 backdrop-blur-xl sm:p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-violet-200/80">Agent feed</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Sequential reasoning in motion</h2>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">Live mock stream</span>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        {orderedAgents.map((agent) => (
          <AgentCard key={agent.name} agent={agent} />
        ))}
      </div>
    </section>
  );
}

export default AgentFeed;
