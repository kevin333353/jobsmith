"""T2：SqliteSaver 持久化——跨「重啟」（新 graph 實例 + 新連線、同一檔案 db）仍能 resume。"""
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app import graph as graph_mod
from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter,
    InterviewKit, CritiqueReport,
)


def _patch_agents(monkeypatch):
    monkeypatch.setattr(graph_mod, "parse_job",
                        lambda jd: ParsedJob(title="AI 工程師", company="未來智能"))
    monkeypatch.setattr(graph_mod, "match_profile",
                        lambda job, profile: MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    monkeypatch.setattr(graph_mod, "research_company", lambda name: CompanyBrief(company=name))
    monkeypatch.setattr(graph_mod, "tailor_resume",
                        lambda job, profile, feedback=None: TailoredResume(summary="履歷"))
    monkeypatch.setattr(graph_mod, "write_cover_letter",
                        lambda job, profile, company, feedback=None: CoverLetter(body="信"))
    monkeypatch.setattr(graph_mod, "prepare_interview",
                        lambda job, profile, company, feedback=None: InterviewKit())
    monkeypatch.setattr(graph_mod, "critique_package",
                        lambda job, r, c, k: CritiqueReport(resume_score=90, cover_letter_score=90,
                                                            interview_score=90, overall_pass=True))


def _initial(profile):
    return {
        "jd_text": "JD", "profile": profile,
        "parsed_job": None, "match_report": None, "company_brief": None,
        "tailored_resume": None, "cover_letter": None, "interview_kit": None,
        "critique": None, "revision_count": 0, "approved": None,
        "errors": [], "telemetry": [],
    }


def test_checkpoint_survives_process_restart(tmp_path, monkeypatch, demo_profile):
    _patch_agents(monkeypatch)
    db = str(tmp_path / "cp.sqlite")

    def make_graph():
        conn = sqlite3.connect(db, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        return graph_mod.build_graph(checkpointer=saver)

    config = {"configurable": {"thread_id": "restart-thread"}}

    # 第一個程序：跑到人工核可關卡（interrupt）後「結束」
    g1 = make_graph()
    result = g1.invoke(_initial(demo_profile), config)
    assert "__interrupt__" in result               # 停在 human_gate
    del g1                                          # 模擬程序結束

    # 第二個程序：全新 graph 實例 + 全新連線、同一檔案 db → 應仍記得該 thread 卡在哪
    g2 = make_graph()
    snap = g2.get_state(config)
    assert snap.next                                # 仍有待跑節點（human_gate）
    assert snap.values["match_report"].score == 82  # 先前狀態完整保存

    # 在「重啟後」核可 → 完成
    g2.invoke(Command(resume="y"), config)
    final = g2.get_state(config).values
    assert final["approved"] is True
