from __future__ import annotations

from dataclasses import dataclass, field

from langgraph.graph import END, START, StateGraph

from graph.routers import (
    route_after_archive,
    route_after_eligibility,
    route_after_review,
)
from nodes import (
    archive_node,
    eligibility_node,
    init_node,
    judge_node,
    make_repair_node,
    review_node,
    select_candidate_node,
    skip_node,
)
from nodes.repair import RepairHandler
from schemas import GraphState


@dataclass(frozen=True)
class NodeBindings:
    discover: RepairHandler
    tech: RepairHandler
    market: RepairHandler
    competitor: RepairHandler
    synergy: RepairHandler
    report: RepairHandler
    repair_handlers: dict[str, RepairHandler] = field(default_factory=dict)


def build_graph(bindings: NodeBindings):
    repair_handlers = {
        "discover": bindings.discover,
        "tech": bindings.tech,
        "market": bindings.market,
        "competitor": bindings.competitor,
        "synergy": bindings.synergy,
        **bindings.repair_handlers,
    }
    builder = StateGraph(GraphState)
    builder.add_node("init", init_node)
    builder.add_node("select_candidate", select_candidate_node)
    builder.add_node("discover", bindings.discover)
    builder.add_node("eligibility", eligibility_node)
    builder.add_node("skip", skip_node)
    builder.add_node("tech", bindings.tech)
    builder.add_node("market", bindings.market)
    builder.add_node("competitor", bindings.competitor)
    builder.add_node("synergy", bindings.synergy)
    builder.add_node("review", review_node)
    builder.add_node("repair", make_repair_node(repair_handlers))
    builder.add_node("judge", judge_node)
    builder.add_node("archive", archive_node)
    builder.add_node("report", bindings.report)
    builder.add_edge(START, "init")
    builder.add_edge("init", "select_candidate")
    builder.add_edge("select_candidate", "discover")
    builder.add_edge("discover", "eligibility")
    builder.add_conditional_edges(
        "eligibility",
        route_after_eligibility,
        {"tech": "tech", "skip": "skip"},
    )
    builder.add_edge("tech", "market")
    builder.add_edge("tech", "competitor")
    builder.add_edge("tech", "synergy")
    builder.add_edge(["market", "competitor", "synergy"], "review")
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"repair": "repair", "judge": "judge"},
    )
    builder.add_edge("repair", "review")
    builder.add_edge("judge", "archive")
    builder.add_edge("skip", "archive")
    builder.add_conditional_edges(
        "archive",
        route_after_archive,
        {"select_candidate": "select_candidate", "report": "report"},
    )
    builder.add_edge("report", END)
    return builder.compile()
