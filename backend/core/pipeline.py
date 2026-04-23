"""Grafo LangGraph linear — fase 1."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from workshop.backend.agents.asset_agent import asset_agent
from workshop.backend.agents.metadata_agent import metadata_agent
from workshop.backend.agents.publisher_agent import publisher_agent
from workshop.backend.agents.research_agent import research_agent
from workshop.backend.agents.script_agent import script_agent
from workshop.backend.agents.thumbnail_card_agent import thumbnail_card_agent
from workshop.backend.agents.tts_agent import tts_agent
from workshop.backend.core.state import VideoState
from workshop.gpu.agents.composer_agent import composer_agent
from workshop.gpu.agents.visual_agent import visual_agent


def build_pipeline():
    graph = StateGraph(VideoState)
    graph.add_node("research_agent", research_agent)
    graph.add_node("script_agent", script_agent)
    graph.add_node("asset_agent", asset_agent)
    graph.add_node("visual_agent", visual_agent)
    graph.add_node("tts_agent", tts_agent)
    graph.add_node("composer_agent", composer_agent)
    graph.add_node("metadata_agent", metadata_agent)
    graph.add_node("thumbnail_card_agent", thumbnail_card_agent)
    graph.add_node("publisher_agent", publisher_agent)

    graph.set_entry_point("research_agent")
    graph.add_edge("research_agent", "script_agent")
    graph.add_edge("script_agent", "asset_agent")
    graph.add_edge("asset_agent", "visual_agent")
    graph.add_edge("visual_agent", "tts_agent")
    graph.add_edge("tts_agent", "composer_agent")
    graph.add_edge("composer_agent", "metadata_agent")
    graph.add_edge("metadata_agent", "thumbnail_card_agent")
    graph.add_edge("thumbnail_card_agent", "publisher_agent")
    graph.add_edge("publisher_agent", END)
    return graph.compile()
