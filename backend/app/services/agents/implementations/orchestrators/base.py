from __future__ import annotations

from .typing import AgentMap
from ...base import BaseAgent
from ...model_adapter import OpenAIModelAdapter, default_log_sink
from ...state import AgentState


class BaseOrchestrator:
    def __init__(self, adapter: OpenAIModelAdapter | None = None) -> None:
        self.adapter = adapter or OpenAIModelAdapter(log_sink=default_log_sink())
        self._agents: AgentMap = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> BaseAgent:
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"Agent not registered: {name}")
        return agent

    async def run_steps(self, state: AgentState, steps: list[str]) -> AgentState:
        for step in steps:
            agent = self.get_agent(step)
            await agent.run(state)
            if state.errors:
                break
        return state
