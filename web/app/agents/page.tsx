"use client";

import { useEffect, useState } from "react";

interface AgentVitals {
  app_id: string;
  ticks: number;
  vitals: {
    uptime_s: number;
    ticks: number;
    tool_calls: number;
    tool_success: number;
    errors: number;
    success_rate: number;
    wellbeing: number;
  };
  open_goals: string[];
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentVitals[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/agents")
      .then((res) => res.json())
      .then((data) => {
        setAgents(Array.isArray(data.agents) ? data.agents : []);
      })
      .catch(() => setAgents([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8 overflow-auto">
      <h1 className="text-3xl font-bold mb-6">Active Agents</h1>
      {loading ? (
        <div className="text-gray-500">Loading agents...</div>
      ) : agents.length === 0 ? (
        <div className="text-gray-500 bg-gray-100 p-4 rounded text-center">
          No active agents loaded.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((agent, i) => (
            <div
              key={i}
              className="border border-gray-200 p-5 rounded-xl shadow-sm bg-white"
            >
              <h3 className="font-bold text-lg">{agent.app_id}</h3>
              <p className="text-gray-500 text-sm mt-1">
                Ticks: {agent.ticks}
              </p>
              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                <div className="bg-gray-50 p-2 rounded">
                  <span className="block text-gray-500">Success Rate</span>
                  <span className="font-semibold">
                    {((agent.vitals?.success_rate ?? 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="bg-gray-50 p-2 rounded">
                  <span className="block text-gray-500">Wellbeing</span>
                  <span className="font-semibold">
                    {((agent.vitals?.wellbeing ?? 0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              {agent.open_goals.length > 0 && (
                <div className="mt-4">
                  <span className="text-xs font-semibold text-gray-500 uppercase">
                    Open Goals
                  </span>
                  <ul className="mt-1 list-disc list-inside text-sm text-gray-700">
                    {agent.open_goals.map((goal, idx) => (
                      <li key={idx}>{goal}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
