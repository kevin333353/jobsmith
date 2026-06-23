"""Supervisor 骨架：parse -> match -> 條件分支。

M1 中兩條分支都指向 END（fan-out 屬 M2）；route_after_match 的決策邏輯
先建立好，M2 只需把 "proceed" 改接到 fan-out 節點。
"""
from langgraph.graph import StateGraph, START, END

from app.state import CopilotState
from app.agents.parse import parse_job
from app.agents.match import match_profile


def parse_node(state: CopilotState) -> dict:
    return {"parsed_job": parse_job(state["jd_text"])}


def match_node(state: CopilotState) -> dict:
    report = match_profile(state["parsed_job"], state["profile"])
    return {"match_report": report}


def route_after_match(state: CopilotState) -> str:
    """依匹配結果決定續做或收手。"""
    report = state["match_report"]
    return "proceed" if report.recommend_proceed else "stop"


def build_graph():
    g = StateGraph(CopilotState)
    g.add_node("parse", parse_node)
    g.add_node("match", match_node)
    g.add_edge(START, "parse")
    g.add_edge("parse", "match")
    g.add_conditional_edges(
        "match",
        route_after_match,
        {"proceed": END, "stop": END},  # M2 會把 proceed 改接 fan-out
    )
    return g.compile()
