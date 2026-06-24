from app.store import memory


def test_profile_roundtrip():
    memory.save_profile({"name": "王", "raw_text": "x"})
    assert memory.get_memory()["profile"]["name"] == "王"


def test_preferences_roundtrip():
    memory.save_preferences({"tone": "自信", "emphasize_skills": ["LLM"]})
    m = memory.get_memory()
    assert m["preferences"]["tone"] == "自信" and m["preferences"]["emphasize_skills"] == ["LLM"]


def test_partial_update_keeps_other_field():
    memory.save_profile({"name": "李"})
    memory.save_preferences({"tone": "務實"})
    m = memory.get_memory()
    assert m["profile"]["name"] == "李"        # 存偏好不該洗掉履歷
    assert m["preferences"]["tone"] == "務實"
