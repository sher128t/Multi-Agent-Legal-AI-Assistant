"""Agent graph orchestrating junior, compliance, and senior roles."""

from __future__ import annotations

import asyncio
import json
from typing import Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from backend.agents import compliance, junior, senior
from backend.rag.retrieval import HybridRetriever, Snippet


class AgentState(TypedDict, total=False):
    query: str
    case_id: str
    snippets: List[Snippet]
    junior: Dict[str, object]
    compliance: List[Dict[str, object]]
    response: Dict[str, object]


PublisherFn = Optional[Callable[[str, Dict[str, object]], None]]


def _publish(publisher: PublisherFn, event: str, payload: Dict[str, object]) -> None:
    if publisher is None:
        return
    publisher(event, payload)


class RedisPublisher:
    def __init__(self, redis_client, channel: str = "agent-events") -> None:
        self.redis = redis_client
        self.channel = channel

    def __call__(self, event: str, payload: Dict[str, object]) -> None:
        if self.redis is None:
            return
        message = json.dumps({"event": event, "payload": payload})
        asyncio.create_task(self.redis.publish(self.channel, message))


def build_graph(retriever: HybridRetriever, publisher: PublisherFn = None):
    graph = StateGraph(AgentState)

    def retrieve_node(state: AgentState) -> AgentState:
        query = state["query"]
        case_id = state["case_id"]
        snippets = retriever.retrieve(query=query, case_id=case_id)
        if not snippets:
            result = {
                "snippets": [],
                "junior": {"draft": "No supporting materials were found; need more docs.", "citations": []},
                "compliance": [],
                "response": {
                    "final_answer": "No supported answer is available. Please ingest additional documents.",
                    "risks": ["Insufficient citations"],
                    "next_steps": ["Provide more case materials."],
                    "citations": [],
                },
            }
            _publish(publisher, "retrieve.miss", {"case_id": case_id})
            return result
        payload = {"count": len(snippets), "case_id": case_id}
        _publish(publisher, "retrieve.complete", payload)
        return {"snippets": snippets}

    def junior_node(state: AgentState) -> AgentState:
        if "response" in state:
            return {}
        output = junior.answer(state["query"], state.get("snippets", []))
        _publish(publisher, "junior.complete", {"citations": len(output.get("citations", []))})
        return {"junior": output}

    def compliance_node(state: AgentState) -> AgentState:
        if "response" in state:
            return {}
        findings = compliance.check(state.get("snippets", []))
        _publish(publisher, "compliance.complete", {"issues": len(findings)})
        return {"compliance": findings}

    def senior_node(state: AgentState) -> AgentState:
        if "response" in state:
            return {}
        jr = state.get("junior", {"draft": "", "citations": []})
        findings = state.get("compliance", [])
        response = senior.synthesize(jr.get("draft", ""), jr.get("citations", []), findings)
        _publish(publisher, "senior.complete", {"citations": len(response.get("citations", []))})
        return {"response": response}

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("junior", junior_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("senior", senior_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "junior")
    graph.add_edge("junior", "compliance")
    graph.add_edge("compliance", "senior")
    graph.add_edge("senior", END)

    return graph.compile()


__all__ = ["AgentState", "build_graph", "RedisPublisher"]

