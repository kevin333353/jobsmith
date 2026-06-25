from app.agents.skill_gap import analyze_skill_gap
from app.agents.skill_lexicon import extract_skills
from app.models import Profile, JobPosting


def test_gap_and_demand():
    jobs = [
        JobPosting(source="x", title="t", company="c", url="u", requirements=["Python", "LLM"]),
        JobPosting(source="x", title="t", company="c", url="u2", requirements=["Python", "Docker"]),
    ]
    prof = Profile(name="a", summary="", skills=["Python"], raw_text="")
    rep = analyze_skill_gap(prof, jobs)
    demand = {d.skill: d.count for d in rep.top_demand}
    assert demand["Python"] == 2
    gaps = {g.skill for g in rep.your_gaps}
    assert "LLM" in gaps and "Docker" in gaps and "Python" not in gaps   # 已具備不算缺口
    assert "Python" in rep.have


def test_extracts_from_title_and_snippet_when_no_requirements():
    # 104 / LinkedIn 常沒有 requirements，只有標題/摘要 → 仍要能貢獻技能需求。
    jobs = [
        JobPosting(source="linkedin", title="Machine Learning Engineer", company="c", url="u"),
        JobPosting(source="104", title="AI 工程師", company="c", url="u2",
                   snippet="需要 Python、PyTorch 與 LLM 經驗"),
    ]
    prof = Profile(name="a", summary="", skills=["Python"], raw_text="")
    rep = analyze_skill_gap(prof, jobs)
    demand = {d.skill for d in rep.top_demand}
    assert {"machine learning", "AI", "Python", "PyTorch", "LLM"} <= demand
    gaps = {g.skill for g in rep.your_gaps}
    assert "PyTorch" in gaps and "LLM" in gaps and "Python" not in gaps


def test_ignores_non_skill_tag_noise():
    # cake/yourator 的 tag 常含「Full-time / Remote / 台北」等非技能雜訊，不應計入需求。
    jobs = [JobPosting(source="cake", title="t", company="c", url="u",
                       requirements=["Full-time", "Remote", "台北", "Python"])]
    prof = Profile(name="a", summary="", skills=[], raw_text="")
    rep = analyze_skill_gap(prof, jobs)
    assert {d.skill for d in rep.top_demand} == {"Python"}   # 雜訊全濾掉，只剩真技能


def test_chinese_resume_covers_english_canonical():
    # 履歷寫中文「機器學習」，職缺要求英文 → 應視為已具備、不列缺口。
    jobs = [JobPosting(source="x", title="Machine Learning Engineer", company="c", url="u")]
    prof = Profile(name="a", summary="專長機器學習與深度學習，做過推薦系統", skills=[], raw_text="")
    rep = analyze_skill_gap(prof, jobs)
    assert "machine learning" in rep.have
    assert "machine learning" not in {g.skill for g in rep.your_gaps}


def test_skill_in_summary_counts_as_owned():
    # 技能只出現在摘要/職稱（不在 skills 欄位）也算具備：摘要含 AI → 具備 canonical「AI」。
    jobs = [JobPosting(source="x", title="t", company="c", url="u", requirements=["AI", "Rust"])]
    prof = Profile(name="a", summary="AI 工程師，專長 LLM 應用與多代理系統",
                   skills=["Python"], raw_text="")
    rep = analyze_skill_gap(prof, jobs)
    gaps = {g.skill for g in rep.your_gaps}
    assert "AI" not in gaps and "AI" in rep.have   # 摘要已涵蓋
    assert "Rust" in gaps                            # 真的沒有


def test_short_ascii_skill_uses_word_boundary():
    # 「ai」不應誤中含 ai 的無關字（rails / domain），「git」不應誤中 github。
    assert "AI" not in extract_skills("rails domain driven design")
    assert "Git" not in extract_skills("我用 github 管版本")
    assert "AI" in extract_skills("資深 AI 工程師")


def test_case_insensitive_and_empty():
    jobs = [JobPosting(source="x", title="t", company="c", url="u", requirements=["python", ""])]
    prof = Profile(name="a", summary="", skills=["PYTHON"], raw_text="")
    rep = analyze_skill_gap(prof, jobs)
    assert not rep.your_gaps                       # python 已具備（大小寫不敏感），空字串忽略
    assert rep.top_demand[0].skill == "Python"     # 回傳 canonical 名稱
