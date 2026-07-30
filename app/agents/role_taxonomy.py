"""Deterministic occupation-title taxonomy used by no-AI discovery.

The taxonomy is intentionally small and auditable.  It normalizes common
Traditional-Chinese and English titles without embeddings or an external model.
Unknown titles are still preserved and searched verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RoleDefinition:
    canonical: str
    aliases: tuple[str, ...]
    markers: tuple[str, ...] = ()

    @property
    def search_variants(self) -> tuple[str, ...]:
        return (self.canonical, *self.aliases)


ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        "AI 工程師",
        ("AI Engineer", "Machine Learning Engineer"),
        ("llm", "rag", "machine learning", "機器學習", "人工智慧", "pytorch"),
    ),
    RoleDefinition(
        "全端工程師",
        ("Full Stack Engineer", "Full Stack Developer"),
        ("full stack", "full-stack", "全端"),
    ),
    RoleDefinition(
        "前端工程師",
        ("Frontend Engineer", "Frontend Developer"),
        ("frontend", "front-end", "前端", "react", "vue"),
    ),
    RoleDefinition(
        "後端工程師",
        ("Backend Engineer", "Backend Developer"),
        ("backend", "back-end", "後端", "fastapi", "django", "spring boot"),
    ),
    RoleDefinition(
        "資料工程師",
        ("Data Engineer",),
        ("data engineer", "資料工程", "數據工程", "etl", "airflow", "spark"),
    ),
    RoleDefinition(
        "資料分析師",
        ("Data Analyst", "Business Intelligence Analyst"),
        ("data analyst", "資料分析", "數據分析", "tableau", "power bi"),
    ),
    RoleDefinition(
        "DevOps 工程師",
        ("DevOps Engineer", "Site Reliability Engineer", "SRE"),
        ("devops", "site reliability", "kubernetes", "terraform", "ci/cd"),
    ),
    RoleDefinition(
        "產品經理",
        ("Product Manager", "Product Owner"),
        ("product manager", "product owner", "產品管理", "產品經理", "roadmap"),
    ),
    RoleDefinition(
        "專案經理",
        ("Project Manager", "Program Manager"),
        ("project manager", "program manager", "專案管理", "專案經理", "pmp"),
    ),
    RoleDefinition(
        "UI/UX 設計師",
        ("UI/UX Designer", "UX Designer", "Product Designer"),
        ("ui/ux", "ux designer", "product designer", "使用者體驗", "figma"),
    ),
    RoleDefinition(
        "視覺設計師",
        ("Graphic Designer", "Visual Designer"),
        ("graphic designer", "visual designer", "平面設計", "視覺設計"),
    ),
    RoleDefinition(
        "行銷企劃",
        ("Marketing Specialist", "Digital Marketing Specialist"),
        ("marketing", "行銷", "seo", "sem", "社群經營", "廣告投放"),
    ),
    RoleDefinition(
        "業務開發",
        ("Business Development", "Sales Representative", "Account Executive"),
        ("business development", "account executive", "業務開發", "業務代表", "銷售"),
    ),
    RoleDefinition(
        "行政人員",
        ("Administrative Assistant", "Administrative Specialist", "Office Administrator"),
        ("行政助理", "行政專員", "行政人員", "辦公室行政", "文書處理"),
    ),
    RoleDefinition(
        "秘書",
        ("Executive Assistant", "Secretary"),
        ("執行長助理", "主管助理", "高階主管助理", "秘書"),
    ),
    RoleDefinition(
        "國際貿易",
        ("International Trade Specialist", "Import Export Specialist"),
        ("國際貿易", "進出口", "國貿", "報關"),
    ),
    RoleDefinition(
        "活動企劃",
        ("Event Planner", "Event Coordinator"),
        ("event planner", "event coordinator", "活動企劃", "活動執行", "會展"),
    ),
    RoleDefinition(
        "公關",
        ("Public Relations Specialist", "PR Specialist"),
        ("public relations", "pr specialist", "公關", "媒體關係"),
    ),
    RoleDefinition(
        "零售門市",
        ("Retail Associate", "Store Associate"),
        ("retail associate", "store associate", "門市人員", "門市專員", "店員", "零售"),
    ),
    RoleDefinition(
        "店長",
        ("Store Manager", "Retail Store Manager"),
        ("store manager", "店長", "門市管理"),
    ),
    RoleDefinition(
        "餐飲服務",
        ("Food Service Staff", "Restaurant Staff", "Server"),
        ("food service", "restaurant staff", "餐飲服務", "外場服務", "餐廳服務", "服務生"),
    ),
    RoleDefinition(
        "廚師",
        ("Chef", "Cook"),
        ("chef", "cook", "廚師", "中餐廚師", "西餐廚師"),
    ),
    RoleDefinition(
        "咖啡師",
        ("Barista",),
        ("barista", "咖啡師", "咖啡沖煮"),
    ),
    RoleDefinition(
        "旅宿服務",
        ("Hotel Staff", "Front Desk Agent", "Guest Service Agent"),
        ("hotel staff", "front desk agent", "飯店櫃檯", "旅館櫃檯", "房務", "旅宿"),
    ),
    RoleDefinition(
        "物流專員",
        ("Logistics Specialist", "Logistics Coordinator"),
        ("logistics specialist", "logistics coordinator", "物流專員", "物流管理", "運輸調度"),
    ),
    RoleDefinition(
        "倉儲人員",
        ("Warehouse Specialist", "Warehouse Operator"),
        ("warehouse specialist", "warehouse operator", "倉儲", "倉管", "理貨"),
    ),
    RoleDefinition(
        "司機",
        ("Driver", "Delivery Driver"),
        ("delivery driver", "司機", "駕駛", "配送員", "送貨"),
    ),
    RoleDefinition(
        "生產作業員",
        ("Production Operator", "Manufacturing Operator"),
        ("production operator", "manufacturing operator", "作業員", "生產線", "製造作業"),
    ),
    RoleDefinition(
        "生產管理",
        ("Production Planner", "Production Manager"),
        ("production planner", "production manager", "生產管理", "生管", "產能規劃"),
    ),
    RoleDefinition(
        "品質管理",
        ("Quality Engineer", "Quality Assurance Specialist", "QC Engineer"),
        ("quality engineer", "quality assurance", "品質管理", "品質保證", "品保", "品管"),
    ),
    RoleDefinition(
        "機械工程師",
        ("Mechanical Engineer", "Mechanical Design Engineer"),
        ("mechanical engineer", "機械工程師", "機構工程師", "機械設計", "solidworks"),
    ),
    RoleDefinition(
        "電機工程師",
        ("Electrical Engineer", "Controls Engineer"),
        ("electrical engineer", "controls engineer", "電機工程師", "電氣工程師", "電控工程師"),
    ),
    RoleDefinition(
        "電子工程師",
        ("Electronics Engineer", "Hardware Engineer"),
        ("electronics engineer", "hardware engineer", "電子工程師", "硬體工程師", "電路設計"),
    ),
    RoleDefinition(
        "半導體工程師",
        ("Semiconductor Engineer", "Process Engineer"),
        ("semiconductor engineer", "半導體", "製程工程師", "設備工程師", "晶圓"),
    ),
    RoleDefinition(
        "維修技術員",
        ("Maintenance Technician", "Service Technician"),
        ("maintenance technician", "service technician", "維修技術員", "設備維護", "機台維修"),
    ),
    RoleDefinition(
        "土木工程師",
        ("Civil Engineer", "Structural Engineer"),
        ("civil engineer", "structural engineer", "土木工程師", "結構工程師"),
    ),
    RoleDefinition(
        "建築設計",
        ("Architect", "Architectural Designer"),
        ("architectural designer", "建築師", "建築設計"),
    ),
    RoleDefinition(
        "工地管理",
        ("Site Engineer", "Construction Manager"),
        ("site engineer", "construction manager", "工地主任", "工地管理", "現場工程師", "營造"),
    ),
    RoleDefinition(
        "不動產業務",
        ("Real Estate Agent", "Property Consultant"),
        ("real estate agent", "property consultant", "房仲", "不動產業務", "不動產經紀", "租賃顧問"),
    ),
    RoleDefinition(
        "護理師",
        ("Registered Nurse", "Nurse"),
        ("registered nurse", "護理師", "護理人員", "臨床護理"),
    ),
    RoleDefinition(
        "醫師",
        ("Physician", "Medical Doctor"),
        ("physician", "medical doctor", "醫師", "住院醫師", "主治醫師"),
    ),
    RoleDefinition(
        "藥師",
        ("Pharmacist",),
        ("pharmacist", "藥師", "藥劑師"),
    ),
    RoleDefinition(
        "醫事技術",
        ("Medical Technologist", "Allied Health Professional"),
        ("medical technologist", "醫檢師", "放射師", "物理治療師", "職能治療師"),
    ),
    RoleDefinition(
        "教師",
        ("Teacher", "Educator"),
        ("teacher", "educator", "教師", "班級經營", "課程設計"),
    ),
    RoleDefinition(
        "補教老師",
        ("Tutor", "Cram School Teacher"),
        ("tutor", "補習班老師", "補教老師", "家教"),
    ),
    RoleDefinition(
        "法務",
        ("Legal Specialist", "Legal Counsel", "Compliance Specialist"),
        ("legal specialist", "legal counsel", "compliance specialist", "法務", "法遵", "合約審閱"),
    ),
    RoleDefinition(
        "律師",
        ("Attorney", "Lawyer"),
        ("attorney", "lawyer", "律師"),
    ),
    RoleDefinition(
        "研究員",
        ("Researcher", "Research Assistant"),
        ("researcher", "research assistant", "研究員", "研究助理", "實驗設計"),
    ),
    RoleDefinition(
        "編輯",
        ("Editor", "Content Editor"),
        ("content editor", "編輯", "內容編輯", "文字編輯"),
    ),
    RoleDefinition(
        "記者",
        ("Journalist", "Reporter"),
        ("journalist", "reporter", "記者", "新聞採訪"),
    ),
    RoleDefinition(
        "影音製作",
        ("Video Editor", "Videographer", "Content Producer"),
        ("video editor", "videographer", "影音製作", "影片剪輯", "攝影師"),
    ),
    RoleDefinition(
        "翻譯",
        ("Translator", "Interpreter"),
        ("translator", "interpreter", "翻譯", "口譯", "筆譯"),
    ),
    RoleDefinition(
        "社會工作",
        ("Social Worker", "Case Manager"),
        ("social worker", "社工師", "社會工作", "個案管理"),
    ),
    RoleDefinition(
        "銀行專員",
        ("Banking Specialist", "Bank Teller"),
        ("banking specialist", "bank teller", "銀行櫃員", "銀行專員", "理財專員"),
    ),
    RoleDefinition(
        "保險顧問",
        ("Insurance Agent", "Insurance Advisor"),
        ("insurance agent", "insurance advisor", "保險業務", "保險顧問", "保險經紀"),
    ),
    RoleDefinition(
        "稅務審計",
        ("Auditor", "Tax Specialist"),
        ("auditor", "tax specialist", "審計", "稅務"),
    ),
    RoleDefinition(
        "保全人員",
        ("Security Guard", "Security Officer"),
        ("security guard", "保全人員", "警衛", "駐衛"),
    ),
    RoleDefinition(
        "清潔人員",
        ("Cleaner", "Housekeeper"),
        ("cleaner", "housekeeper", "清潔人員", "環境清潔"),
    ),
    RoleDefinition(
        "美容美髮",
        ("Beautician", "Hair Stylist"),
        (
            "beautician",
            "hair stylist",
            "美容師",
            "美髮師",
            "美髮設計",
            "髮型設計",
            "美甲師",
        ),
    ),
    RoleDefinition(
        "營運專員",
        ("Operations Specialist", "Operations Manager"),
        ("operations", "營運", "營運管理", "流程改善"),
    ),
    RoleDefinition(
        "人力資源",
        ("Human Resources", "HR Specialist", "Recruiter"),
        ("human resources", "hr specialist", "recruiter", "人力資源", "招募"),
    ),
    RoleDefinition(
        "財務會計",
        ("Accountant", "Financial Analyst"),
        ("accountant", "financial analyst", "會計", "財務分析", "財務"),
    ),
    RoleDefinition(
        "客戶成功",
        ("Customer Success", "Customer Success Manager"),
        ("customer success", "客戶成功", "客戶維繫"),
    ),
    RoleDefinition(
        "客服專員",
        ("Customer Service", "Customer Support"),
        ("customer service", "customer support", "客服", "客戶服務"),
    ),
    RoleDefinition(
        "採購供應鏈",
        ("Procurement Specialist", "Supply Chain Specialist"),
        ("procurement", "supply chain", "採購", "供應鏈"),
    ),
)


def _contains(text: str, marker: str) -> bool:
    haystack = (text or "").casefold()
    needle = (marker or "").casefold().strip()
    if not needle:
        return False
    if not needle.isascii():
        return needle in haystack
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None


def definition_for_role(role: str) -> RoleDefinition | None:
    """Return the known family for a canonical, decorated, or aliased title."""
    for definition in ROLE_DEFINITIONS:
        if _contains(role, definition.canonical):
            return definition
        if any(_contains(role, alias) for alias in definition.aliases):
            return definition
    return None


def infer_known_roles(text: str, limit: int = 4) -> list[str]:
    """Infer known role families from resume text in stable priority order."""
    found: list[str] = []
    for definition in ROLE_DEFINITIONS:
        terms = (*definition.search_variants, *definition.markers)
        if any(_contains(text, term) for term in terms):
            found.append(definition.canonical)
        if len(found) >= limit:
            break
    return found


def query_variants(role: str) -> list[str]:
    """Expand a title to auditable Chinese/English search variants."""
    definition = definition_for_role(role)
    if definition is None:
        cleaned = (role or "").strip()
        return [cleaned] if cleaned else []
    return list(definition.search_variants)


def matching_roles(profile_roles: list[str], job_title: str) -> list[str]:
    """Return profile role labels that match a job title."""
    title = (job_title or "").strip()
    title_compact = re.sub(r"[\s/|｜、,，()（）\[\]【】:：-]+", "", title.casefold())
    matched: list[str] = []
    for role in profile_roles:
        cleaned = (role or "").strip()
        if not cleaned:
            continue
        definition = definition_for_role(cleaned)
        if definition is not None:
            if any(
                _contains(title, term)
                for term in (*definition.search_variants, *definition.markers)
            ):
                if definition.canonical not in matched:
                    matched.append(definition.canonical)
                continue
        role_compact = re.sub(r"[\s/|｜、,，()（）\[\]【】:：-]+", "", cleaned.casefold())
        if role_compact and (role_compact in title_compact or title_compact in role_compact):
            if cleaned not in matched:
                matched.append(cleaned)
    return matched
