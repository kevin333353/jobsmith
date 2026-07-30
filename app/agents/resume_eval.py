"""② 履歷健檢 Agent：把履歷全文結構化成 Profile，並做健檢評分。"""
import re

from app.agents.role_taxonomy import infer_known_roles
from app.agents.skill_lexicon import extract_skills
from app.llm import get_llm
from app.models import Profile, ResumeAssessment, ResumeIssue, ResumeRewrite

STRUCTURE_SYSTEM = (
    "你是履歷解析器。請從使用者提供的履歷全文中，抽取結構化欄位："
    "姓名(name)、一句話定位(summary)、技能清單(skills)、經歷條列(experiences)、"
    "學歷(education)、總年資(years_experience)、期望職務(preferred_roles)。"
    "raw_text 欄位請直接填入空字串即可（系統會自行補上原文，不需你回填）。"
    "找不到的欄位留空或 null，不要捏造。"
)

EVAL_SYSTEM = (
    "你是資深台灣科技業招募顧問暨履歷健檢專家。請依台灣求職與 ATS 慣例，對這份履歷評分"
    "（每項 0-100）：整體(overall_score)、表達清晰度(clarity_score)、量化成果(impact_score)、"
    "ATS 關鍵字涵蓋(ats_keyword_score)、台灣履歷慣例符合度(localization_score)、完整度(completeness_score)。"
    "另外提供：一段總評(summary)、優點清單(strengths)、問題清單(issues，每項含 severity=high/medium/low、"
    "area 所在區塊、problem 問題、fix 可照做的具體修正)、以及 2-4 個改寫前後對照範例(rewrite_examples)。"
    "務實具體、不空泛，不要捏造未提供的經歷。全程使用繁體中文。"
)

_EXPERIENCE_MARKERS = (
    "built", "developed", "designed", "implemented", "managed", "led", "optimized",
    "created", "improved", "reduced", "increased", "coordinated", "served", "maintained",
    "processed", "prepared", "assisted", "taught", "cared", "sold", "audited", "inspected",
    "operated", "負責", "開發", "建立", "導入", "優化", "管理", "協調", "執行", "規劃",
    "服務", "維護", "處理", "教學", "照護", "銷售", "稽核", "檢驗", "操作", "達成",
)
_EDUCATION_MARKERS = (
    "university", "college", "bachelor", "master", "phd", "degree",
    "大學", "學院", "學士", "碩士", "博士", "學歷",
)
_CONTACT_OR_URL_RE = re.compile(r"(@|https?://|www\.|linkedin|github|09\d{2})", re.IGNORECASE)
_CJK_NAME_RE = re.compile(r"^[\u3400-\u9fff]{2,4}$")
_COMMON_CJK_SURNAMES = set(
    "王李張陳劉楊黃趙吳周徐孫馬朱胡郭何高林羅鄭梁謝宋唐許韓馮鄧曹彭曾蕭田董潘袁蔡蔣余于杜葉程魏蘇呂丁任沈姚盧姜崔鍾譚陸汪范金石廖賈夏韋付方白鄒孟熊秦邱江尹薛閻段雷侯龍史陶黎賀顧毛郝龔邵萬錢嚴覃武戴莫孔向湯"
)
_NAME_STOPWORDS = {
    "狀在中", "在中", "工作", "年資", "學歷", "專長", "技能", "希望", "上日", "希面", "可上",
}
_NAME_BAD_FRAGMENTS = (
    "狀", "工作", "職務", "希望", "地址", "電話", "手機", "主手", "mail", "email",
    "學歷", "大學", "公司", "工程師", "履歷", "求職", "年", "月", "日",
)


def _resume_lines(resume_text: str) -> list[str]:
    return [line.strip(" \t•*-|") for line in (resume_text or "").splitlines() if line.strip()]


def _looks_like_name(line: str) -> bool:
    clean = line.strip()
    if not (2 <= len(clean) <= 60) or _CONTACT_OR_URL_RE.search(clean):
        return False
    if clean in _NAME_STOPWORDS:
        return False
    lowered = clean.lower()
    role_words = (
        "engineer", "developer", "designer", "manager", "analyst", "intern",
        "resume", "cv", "portfolio", "profile",
    )
    if any(word in lowered for word in role_words):
        return False
    if any(fragment in lowered for fragment in _NAME_BAD_FRAGMENTS):
        return False
    if sum(ch.isdigit() for ch in clean) > 2:
        return False
    words = clean.split()
    return len(words) <= 4


def _name_score(line: str, index: int) -> int:
    clean = line.strip()
    if not _looks_like_name(clean):
        return -1
    score = max(0, 80 - min(index, 40))
    if _CJK_NAME_RE.fullmatch(clean):
        score += 50
        if clean[0] in _COMMON_CJK_SURNAMES:
            score += 80
        if 2 <= len(clean) <= 3:
            score += 15
    elif re.fullmatch(r"[A-Za-z][A-Za-z'.-]+(?:\s+[A-Za-z][A-Za-z'.-]+){0,3}", clean):
        score += 50
    return score


def _infer_name(lines: list[str]) -> str:
    candidates = [
        (_name_score(line, idx), line)
        for idx, line in enumerate(lines[:40])
    ]
    candidates = [(score, line) for score, line in candidates if score >= 0]
    if not candidates:
        return "未命名候選人"
    return max(candidates, key=lambda item: item[0])[1]


# 職稱關鍵詞：用來從履歷上方那行（常是「產品經理 / Product Manager」）認出職稱，
# 讓非軟體履歷在 AI 降級時也別一律塌成「工程師」。
_TITLE_WORDS = (
    "經理", "工程師", "設計師", "分析師", "規劃師", "架構師", "總監", "協理", "副理",
    "專員", "主任", "組長", "課長", "顧問", "助理", "業務", "行銷", "企劃", "採購",
    "會計", "財務", "人資", "客服", "編輯", "記者", "醫師", "護理", "教師", "律師",
    "行政人員", "秘書", "法務", "研究員", "研究助理", "門市", "店長", "店員",
    "服務員", "服務生", "廚師", "咖啡師", "司機", "駕駛", "作業員", "技術員",
    "操作員", "倉管", "理貨", "保全", "警衛", "清潔", "房務", "藥師", "社工師",
    "翻譯", "房仲", "美容師", "美髮師",
    "manager", "engineer", "developer", "designer", "analyst", "architect",
    "director", "specialist", "consultant", "lead", "scientist", "coordinator",
    "associate", "officer", "accountant", "marketing", "sales", "nurse", "physician",
    "pharmacist", "teacher", "attorney", "lawyer", "researcher", "editor", "journalist",
    "reporter", "driver", "chef", "cook", "barista", "technician", "operator",
    "administrator", "secretary", "clerk", "server", "cashier", "warehouse", "security",
    "cleaner", "housekeeper", "translator", "interpreter",
)
_TITLE_SPLIT_RE = re.compile(r"[/|｜、,，()（）\[\]【】:：]")
_EXPLICIT_YEARS_PATTERNS = (
    re.compile(
        r"(?:總年資|工作年資|年資|工作經驗|相關經驗|專業經驗|experience)"
        r"\s*[:：]?\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:年|years?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:年|years?)"
        r"\s*(?:以上)?\s*(?:工作|相關|專業)?\s*(?:經驗|experience)",
        re.IGNORECASE,
    ),
)


def _infer_title_role(lines: list[str]) -> str:
    """從履歷最上方找最像『職稱』的一行，回傳清理後的中文職稱片段（找不到回空字串）。"""
    for line in lines[:8]:
        lowered = line.lower()
        if not any(w in line or w in lowered for w in _TITLE_WORDS):
            continue
        # 取分隔符前段（「產品經理 / Product Manager」→「產品經理」），去頭尾雜訊。
        head = _TITLE_SPLIT_RE.split(line)[0].strip(" \t#·•|/")
        if 2 <= len(head) <= 20 and not _CONTACT_OR_URL_RE.search(head):
            return head
    return ""


def _infer_roles(resume_text: str, skills: list[str]) -> list[str]:
    blob = " ".join([resume_text or "", " ".join(skills)])
    title = _infer_title_role(_resume_lines(resume_text))
    title_roles = infer_known_roles(title, limit=1) if title else []
    roles = title_roles + [
        role for role in infer_known_roles(blob, limit=4)
        if role not in title_roles
    ]
    if roles:
        return roles[:4]
    # 詞庫全沒中 → 先用履歷自己的職稱行，最後才退到泛稱。
    return [title] if title else ["一般職缺"]


def _infer_years_experience(resume_text: str) -> float | None:
    """Read only explicit experience statements; do not infer from date ranges."""
    candidates: list[float] = []
    for pattern in _EXPLICIT_YEARS_PATTERNS:
        for raw in pattern.findall(resume_text or ""):
            try:
                years = float(raw)
            except (TypeError, ValueError):
                continue
            if 0 <= years <= 50:
                candidates.append(years)
    return max(candidates) if candidates else None


def _fallback_profile_from_text(resume_text: str) -> Profile:
    lines = _resume_lines(resume_text)
    skills = extract_skills(resume_text)
    roles = _infer_roles(resume_text, skills)
    name = _infer_name(lines)
    skill_text = "、".join(skills[:6]) if skills else "履歷中的專案與工作經驗"
    summary = f"{roles[0]}，具備 {skill_text} 等背景。"
    experiences = [
        line for line in lines
        if any(marker in line.lower() for marker in _EXPERIENCE_MARKERS)
    ][:6]
    education = next(
        (line for line in lines if any(marker in line.lower() for marker in _EDUCATION_MARKERS)),
        "",
    )
    return Profile(
        name=name,
        summary=summary,
        skills=skills,
        experiences=experiences,
        education=education,
        years_experience=_infer_years_experience(resume_text),
        preferred_roles=roles,
        raw_text=resume_text,
        parse_degraded=True,  # 本機備援 → 標記降級，供前端提示使用者檢查 AI 後端
    )


def structure_profile_local(resume_text: str) -> Profile:
    """Resume text → first-class deterministic Profile with zero LLM calls."""
    profile = _fallback_profile_from_text(resume_text)
    profile.parse_degraded = False
    return profile


def _repair_profile(profile: Profile, resume_text: str) -> Profile:
    fallback = _fallback_profile_from_text(resume_text)
    fallback_name = fallback.name.strip()
    profile_name = profile.name.strip()
    if fallback_name and fallback_name != "未命名候選人" and (
        not profile_name
        or profile_name not in resume_text
        or (fallback_name != profile_name and _name_score(profile_name, 0) < 0)
    ):
        profile.name = fallback.name
    if not profile.summary.strip():
        profile.summary = fallback.summary
    if not profile.skills:
        profile.skills = fallback.skills
    if not profile.experiences:
        profile.experiences = fallback.experiences
    if not profile.education:
        profile.education = fallback.education
    if profile.years_experience is None:
        profile.years_experience = fallback.years_experience
    if not profile.preferred_roles:
        profile.preferred_roles = fallback.preferred_roles
    if not profile.raw_text:
        profile.raw_text = resume_text
    return profile


def structure_profile(resume_text: str) -> Profile:
    """履歷全文 → 結構化 Profile（standard 分層）。

    用 sonnet 而非 haiku：履歷解析是後續匹配、排序、技能缺口、產出的共同上游，
    haiku 抽取技能/定位容易漏（例如把「AI 工程師」的核心能力漏掉），改用 sonnet 較穩。

    這是「重點功能」的上游：解析失敗會讓 Profile/關鍵字/排序全部塌成本機備援。故給足
    timeout（CLI 冷啟動載入系統提示偏慢，60 秒易逾時降級）並允許一次重試（結構化輸出
    偶爾吐到不合 schema），盡量讓 AI 解析「成功」，而非太快放棄退到備援。
    """
    try:
        llm = get_llm("standard", timeout=120, structured_retries=2).with_structured_output(Profile)
        profile = llm.invoke([("system", STRUCTURE_SYSTEM), ("human", resume_text)])
    except Exception:
        return _fallback_profile_from_text(resume_text)
    return _repair_profile(profile, resume_text)


def evaluate_resume(resume_text: str, profile: Profile) -> ResumeAssessment:
    """履歷健檢評分（deep 分層）。

    健檢報告欄位多（含巢狀 issues/rewrite_examples），且 deep 為推理模型會額外
    消耗 reasoning tokens，故提高 max_tokens 避免結構化輸出被截斷而無法解析。
    """
    llm = get_llm("deep", max_tokens=6000, timeout=120, structured_retries=1).with_structured_output(ResumeAssessment)
    human = (
        f"【履歷全文】\n{resume_text}\n\n"
        f"【已結構化資料】\n{profile.model_dump_json(indent=2)}"
    )
    return llm.invoke([("system", EVAL_SYSTEM), ("human", human)])


_METRIC_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:%|％|倍|人|萬|k|K|ms|秒|分鐘|小時|天|月|年)|"
    r"提升|降低|減少|成長|節省|優化|改善)"
)
_CONTACT_RE = re.compile(r"(@|09\d{2}[-\s]?\d{3}[-\s]?\d{3}|linkedin|github)", re.IGNORECASE)


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _fallback_role(profile: Profile, resume_text: str) -> str:
    if profile.preferred_roles:
        return profile.preferred_roles[0]
    inferred = _infer_roles(resume_text, profile.skills or [])
    return inferred[0] if inferred else "目標職稱"


def _skill_phrase(skills: list[str], limit: int = 4) -> str:
    picked = [skill for skill in skills if skill][:limit]
    return " / ".join(picked) if picked else "核心技能"


def _evidence_lines(lines: list[str], skills: list[str]) -> list[str]:
    skill_terms = [skill.lower() for skill in skills if skill]
    evidence: list[str] = []
    for line in lines:
        lowered = line.lower()
        has_metric = bool(_METRIC_RE.search(line))
        has_skill = any(term in lowered for term in skill_terms)
        has_action = any(marker in lowered for marker in _EXPERIENCE_MARKERS)
        if has_metric or has_skill or has_action:
            evidence.append(line)
    if not evidence:
        evidence = lines[:2]
    out: list[str] = []
    for line in evidence:
        if line not in out:
            out.append(line)
    return out[:4]


def _primary_metric(text: str) -> str:
    for match in _METRIC_RE.findall(text):
        if re.search(r"\d", match):
            return match.strip()
    return "可量化成果"


def fallback_resume_assessment(
    resume_text: str,
    profile: Profile,
    *,
    reason: str = "",
) -> ResumeAssessment:
    """Return a conservative local assessment when the LLM report is not parseable."""
    text = (resume_text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    metric_hits = _METRIC_RE.findall(text)
    skill_count = len(profile.skills or [])
    target_role = _fallback_role(profile, text)
    skill_phrase = _skill_phrase(profile.skills or [])
    evidence = _evidence_lines(lines, profile.skills or [])
    primary_metric = _primary_metric(text)
    has_contact = bool(_CONTACT_RE.search(text))
    has_education = bool(profile.education or re.search(r"學歷|大學|碩士|博士|學士", text))
    has_experience = bool(profile.experiences or re.search(r"經歷|工作|專案|負責|開發", text))

    completeness = _clamp_score(45 + min(len(text) // 80, 25) + 10 * has_experience
                                + 8 * has_education + 6 * has_contact)
    clarity = _clamp_score(52 + min(len(lines), 12) * 2 + (8 if profile.summary else 0))
    impact = _clamp_score(42 + min(len(metric_hits), 5) * 10)
    ats_keyword = _clamp_score(45 + min(skill_count, 8) * 6)
    localization = _clamp_score(58 + 8 * has_contact + 8 * has_education + 6 * has_experience)
    overall = round((completeness + clarity + impact + ats_keyword + localization) / 5)

    strengths = []
    strengths.append(f"可辨識的目標定位為 {target_role}，可用 {skill_phrase} 做主軸。")
    if profile.summary:
        strengths.append(f"已能辨識出主要定位：{profile.summary}")
    if skill_count:
        strengths.append(f"履歷中可辨識 {skill_count} 項技能，可作為 ATS 關鍵字基礎。")
    if metric_hits:
        strengths.append(f"履歷已有量化成果，例如 {primary_metric}；可再擴大到更多工作經歷。")
    if evidence:
        strengths.append(f"可用原文成果延伸改寫：{evidence[0][:90]}")
    if not strengths:
        strengths.append("履歷已有可分析的基本內容，但需要補強結構與成果描述。")

    issues: list[ResumeIssue] = []
    if len(text) < 700:
        issues.append(ResumeIssue(
            severity="medium",
            area="完整度",
            problem="履歷內容偏短，可能不足以讓招募方判斷職責範圍與成果。",
            fix="補上近 2-3 個代表性專案或工作經歷，每項包含角色、技術、成果與影響。",
        ))
    if len(metric_hits) < 2:
        issues.append(ResumeIssue(
            severity="high",
            area="量化成果",
            problem="可量化成果不足，容易看起來像職責描述而非成就。",
            fix="將『負責開發』改成『用什麼技術完成什麼功能，改善多少時間、成本、品質或使用量』。",
        ))
    if skill_count < 5:
        issues.append(ResumeIssue(
            severity="medium",
            area="ATS 關鍵字",
            problem="可辨識技能偏少，ATS 與招募者快速掃描時可能抓不到核心能力。",
            fix="新增技能區，列出語言、框架、資料庫、雲端、測試、工具與與目標職稱相關的關鍵字。",
        ))
    if not has_contact:
        issues.append(ResumeIssue(
            severity="low",
            area="台灣履歷慣例",
            problem="未明確偵測到聯絡方式或作品連結。",
            fix="確認履歷上方有 Email、手機、LinkedIn/GitHub/作品集，並避免放過多私人資料。",
        ))

    if not issues:
        issues.append(ResumeIssue(
            severity="low",
            area="深度健檢",
            problem="AI 深度報告回覆格式不正確，因此本次只能提供保守備援評估。",
            fix="稍後重試深度健檢；若連續發生，請切換較穩定的 API key 模型或縮短履歷再試。",
        ))

    rewrite_sources = evidence[:2] or (lines[:2] if lines else ["負責後端開發"])
    if len(rewrite_sources) == 1:
        rewrite_sources.append(rewrite_sources[0])
    rewrite_examples = [
        ResumeRewrite(
            original=line[:120],
            improved=(
                f"以 {target_role} 身分使用 {skill_phrase} 完成：{line[:80]}；"
                f"並補上影響範圍、使用者數或效率變化，例如 {primary_metric}。"
            ),
            why="保留原文證據，再補齊角色、技術、成果與量化影響，會比只描述職責更有說服力。",
        )
        for line in rewrite_sources[:2]
    ]

    reason_note = f"原因：{reason}" if reason else "原因：AI 回覆格式不正確。"
    summary = (
        "AI 深度健檢回覆格式不正確，已改用保守備援健檢。"
        "此報告依履歷長度、技能密度、量化成果與台灣履歷慣例做初步評估；"
        "建議稍後重試深度健檢以取得更細的改寫建議。"
        f"{reason_note}"
    )

    return ResumeAssessment(
        assessment_mode="fallback",
        fallback_reason=reason,
        overall_score=overall,
        clarity_score=clarity,
        impact_score=impact,
        ats_keyword_score=ats_keyword,
        localization_score=localization,
        completeness_score=completeness,
        summary=summary,
        strengths=strengths,
        issues=issues,
        rewrite_examples=rewrite_examples,
    )
