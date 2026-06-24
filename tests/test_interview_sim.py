from app.agents import interview_sim as iv
from app.models import (
    Profile, InterviewQuestion, InterviewQuestionList, AnswerFeedback, InterviewSummary,
)
from tests.conftest import FakeLLM


def _p():
    return Profile(name="王", summary="後端工程師", raw_text="…")


def test_generate_questions(monkeypatch):
    canned = InterviewQuestionList(items=[
        InterviewQuestion(category="技術", question="介紹一個你做過的系統"),
    ])
    monkeypatch.setattr(iv, "get_llm", lambda tier: FakeLLM(canned))
    qs = iv.generate_questions("AI 工程師 JD", _p(), n=1)
    assert len(qs) == 1 and qs[0].question == "介紹一個你做過的系統"


def test_generate_questions_caps_at_n(monkeypatch):
    canned = InterviewQuestionList(items=[InterviewQuestion(question=f"q{i}") for i in range(10)])
    monkeypatch.setattr(iv, "get_llm", lambda tier: FakeLLM(canned))
    assert len(iv.generate_questions("JD", _p(), n=6)) == 6


def test_evaluate_answer(monkeypatch):
    fb = AnswerFeedback(score=80, strengths=["具體"], improvements=["量化"], sample_answer="…")
    monkeypatch.setattr(iv, "get_llm", lambda tier: FakeLLM(fb))
    out = iv.evaluate_answer("題", "答", "JD", _p())
    assert out.score == 80 and out.improvements == ["量化"]


def test_summarize(monkeypatch):
    s = InterviewSummary(overall_score=78, summary="整體不錯", advice=["多準備系統設計"])
    monkeypatch.setattr(iv, "get_llm", lambda tier: FakeLLM(s))
    out = iv.summarize("JD", [{"question": "q", "answer": "a"}])
    assert out.overall_score == 78 and out.advice
