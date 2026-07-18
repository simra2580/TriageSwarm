import { useState } from 'react';
import LogInput from './components/LogInput.jsx';
import AgentFeed from './components/AgentFeed.jsx';
import ResultCard from './components/ResultCard.jsx';
import IncidentMemoryCard from './components/IncidentMemoryCard.jsx';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const presetLogs = [
  {
    label: 'Payments checkout',
    value: `2026-07-18 14:32:11 UTC [payments] checkout-api error rate jumped to 18%
2026-07-18 14:32:13 UTC [auth] token refresh retried 6 times and timed out
2026-07-18 14:32:14 UTC [gateway] downstream requests began returning 500s
2026-07-18 14:32:20 UTC [orchestrator] retry budget exhausted, user checkout aborted`,
  },
  {
    label: 'Webhook fanout',
    value: `2026-07-18 09:11:02 UTC [webhooks] fanout queue depth climbed above 400
2026-07-18 09:11:04 UTC [auth] refresh token lookup started returning stale values
2026-07-18 09:11:08 UTC [delivery] duplicate webhook deliveries surged after retries
2026-07-18 09:11:15 UTC [worker] retry loop kept replaying the same payload`,
  },
  {
    label: 'Session invalidation',
    value: `2026-07-18 08:03:22 UTC [auth] login failures spiked after invalidation
2026-07-18 08:03:24 UTC [sessions] tokens were cleared and immediately recreated
2026-07-18 08:03:29 UTC [backend] retries fired with no backoff guard
2026-07-18 08:03:34 UTC [api] repeated requests hit the same failing path`,
  },
  {
    label: 'Rate limit cascade',
    value: `2026-07-18 16:44:01 UTC [gateway] a single caller saturated the shared limiter
2026-07-18 16:44:04 UTC [api] unrelated requests started failing with 429s
2026-07-18 16:44:09 UTC [upstream] retry bursts kept consuming the remaining budget
2026-07-18 16:44:16 UTC [platform] traffic recovered only after the window reset`,
  },
];

const initialLog = presetLogs[0].value;

const agentCatalog = {
  'Log Analyzer': {
    name: 'Log Analyzer',
    role: 'Reads the incident log and extracts the strongest signals.',
    tone: 'amber',
  },
  Historian: {
    name: 'Historian',
    role: 'Searches incidents.json for similar failures.',
    tone: 'violet',
  },
  Hypothesis: {
    name: 'Hypothesis',
    role: 'Turns the evidence into a likely root cause.',
    tone: 'cyan',
  },
  Skeptic: {
    name: 'Skeptic',
    role: 'Challenges weak assumptions and missing context.',
    tone: 'slate',
  },
  'Prevention Architect': {
    name: 'Prevention Architect',
    role: 'Shapes the safest remediation and guardrails.',
    tone: 'cyan',
  },
};

const agentOrder = ['Log Analyzer', 'Historian', 'Hypothesis', 'Skeptic', 'Prevention Architect'];

const defaultResult = [
  { label: 'Likely root cause', value: 'Awaiting analysis', accent: 'from-cyan-400 to-blue-500' },
  { label: 'Recurring pattern', value: 'No historical match yet', accent: 'from-violet-400 to-fuchsia-500' },
  { label: 'Recommended fix', value: 'Run an incident analysis to generate a prevention plan', accent: 'from-amber-300 to-orange-500' },
];

const formatTime = () =>
  new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function formatMatchSummary(match) {
  return `${match.incident_id} • ${match.title} • ${Math.round(match.similarity * 100)}% similar`;
}

function App() {
  const [log, setLog] = useState(initialLog);
  const [selectedPreset, setSelectedPreset] = useState(presetLogs[0].label);
  const [agentFeed, setAgentFeed] = useState([]);
  const [resultItems, setResultItems] = useState(defaultResult);
  const [incidentMemory, setIncidentMemory] = useState([]);
  const [summary, setSummary] = useState('Awaiting the first analysis run.');
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('Disconnected');
  const [confidenceScore, setConfidenceScore] = useState(0);
  const [successStamp, setSuccessStamp] = useState(0);

  function updateAgent(name, patch) {
    setAgentFeed((current) => current.map((agent) => (agent.name === name ? { ...agent, ...patch } : agent)));
  }

  function appendOrUpdateAgent(name, patch) {
    setAgentFeed((current) => {
      const existing = current.find((agent) => agent.name === name);
      if (!existing) {
        const template = agentCatalog[name];
        return [
          ...current,
          {
            ...template,
            name,
            status: 'Thinking',
            timestamp: formatTime(),
            summary: 'Thinking through the incident...',
            details: 'Reading the live stream for signal.',
            confidence: 0,
            progress: 22,
            ...patch,
          },
        ];
      }

      return current.map((agent) => (agent.name === name ? { ...agent, ...patch } : agent));
    });
  }

  async function analyzeIncident() {
    if (loading) return;
    setLoading(true);
    setStatusText('Streaming updates');
    setSummary('Analyzing incident...');
    setAgentFeed([]);
    setResultItems(defaultResult);
    setIncidentMemory([]);
    setConfidenceScore(0);
    setSuccessStamp(0);

    try {
      const response = await fetch(`${API_BASE_URL}/diagnose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ log }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalPayload = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          if (!part.trim()) continue;

          const eventLine = part.split('\n').find((line) => line.startsWith('event: '));
          const dataLine = part.split('\n').find((line) => line.startsWith('data: '));
          if (!eventLine || !dataLine) continue;

          const event = eventLine.slice(7).trim();
          const data = JSON.parse(dataLine.slice(6));

          if (event === 'session_started') {
            setStatusText(data.message ?? 'Streaming updates');
          }

          if (event === 'agent_started') {
            appendOrUpdateAgent(data.agent, {
              status: 'Thinking',
              timestamp: formatTime(),
              summary: 'Thinking through the incident...',
              details: 'Scanning for the strongest signal.',
              confidence: 0,
              progress: 22,
            });
            setStatusText(`${data.agent} is thinking`);
          }

          if (event === 'agent_result') {
            await sleep(220);
            updateAgent(data.agent, {
              status: 'Complete',
              timestamp: formatTime(),
              summary: data.summary,
              details: data.details,
              confidence: data.confidence,
              progress: 100,
              artifacts: data.data ?? {},
            });
          }

          if (event === 'complete') {
            finalPayload = data;
          }
        }
      }

      if (finalPayload) {
        const finalAgent = finalPayload.agents?.[finalPayload.agents.length - 1];
        const finalConfidence = Math.round((finalAgent?.confidence ?? 0) * 100);
        const topMatch = finalPayload.likely_matches?.[0];

        setSummary(finalPayload.summary);
        setResultItems([
          {
            label: 'Likely root cause',
            value: finalPayload.root_cause,
            accent: 'from-cyan-400 to-blue-500',
          },
          {
            label: 'Recurring pattern',
            value: topMatch ? formatMatchSummary(topMatch) : 'New incident pattern detected.',
            accent: 'from-violet-400 to-fuchsia-500',
          },
          {
            label: 'Recommended fix',
            value: finalPayload.prevention[0] ?? 'No prevention plan returned',
            accent: 'from-amber-300 to-orange-500',
          },
        ]);
        setIncidentMemory(
          finalPayload.likely_matches.map((incident) => ({
            id: incident.incident_id,
            title: incident.title,
            date: incident.date,
            summary: incident.summary,
            tags: incident.tags,
            similarity: incident.similarity,
            warning: incident.similarity >= 0.72,
            whySimilar: incident.why_similar,
            matchedKeywords: incident.matched_keywords,
            sharedConcepts: incident.shared_concepts,
          })),
        );
        setConfidenceScore(finalConfidence);
        setSuccessStamp(Date.now());
        setStatusText('Recommendation ready');
      }
    } catch (error) {
      setStatusText('Backend unavailable');
      setSummary(error.message);
      setResultItems([
        { label: 'Likely root cause', value: 'Unable to connect to backend', accent: 'from-cyan-400 to-blue-500' },
        { label: 'Recurring pattern', value: 'Check that FastAPI is running on port 8000', accent: 'from-violet-400 to-fuchsia-500' },
        { label: 'Recommended fix', value: 'Start the backend and retry the analysis', accent: 'from-amber-300 to-orange-500' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const incidentCards = incidentMemory.length
    ? incidentMemory
    : [
        {
          id: 'No matches yet',
          title: 'Run an analysis to populate incident memory',
          date: 'Now',
          summary: 'The historian only surfaces entries from backend/incidents.json.',
          tags: ['historian', 'memory'],
          warning: false,
          whySimilar: 'No comparison yet.',
          matchedKeywords: [],
          sharedConcepts: [],
        },
      ];

  return (
    <main className="min-h-screen bg-[#050816] text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-4">
              <span className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-medium tracking-[0.3em] text-cyan-200 uppercase">
                TriageSwarm
              </span>
              <div className="space-y-3">
                <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                  Incident Memory for fast, multi agent triage.
                </h1>
                <p className="max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                  Drop in an incident log, let specialized agents inspect it, compare it with prior failures, and surface a fix that prevents the same outage from coming back for round two.
                </p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:w-[30rem]">
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 backdrop-blur-lg">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Agents online</p>
                <p className="mt-2 text-2xl font-semibold text-white">05</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 backdrop-blur-lg">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Backend status</p>
                <p className="mt-2 text-2xl font-semibold text-white">{statusText}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4 backdrop-blur-lg">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Confidence</p>
                <p className="mt-2 text-2xl font-semibold text-white">{confidenceScore}%</p>
              </div>
            </div>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            <LogInput
              value={log}
              onChange={setLog}
              onAnalyze={analyzeIncident}
              loading={loading}
              presets={presetLogs}
              selectedPreset={selectedPreset}
              onSelectPreset={(preset) => {
                setSelectedPreset(preset.label);
                setLog(preset.value);
              }}
            />
            <AgentFeed agents={agentFeed} order={agentOrder} />
          </div>

          <div className="space-y-6">
            <ResultCard
              title={summary}
              items={resultItems}
              confidence={confidenceScore}
              readyStamp={successStamp}
            />
            <IncidentMemoryCard incidents={incidentCards} />
          </div>
        </section>
      </div>
    </main>
  );
}

export default App;
