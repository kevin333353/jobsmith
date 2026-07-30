"""技能詞庫：把職缺文字（標題／摘要／要求）對到正規化的技能名稱。

技能缺口分析改用本詞庫萃取，解決兩個資料品質問題：
1. 104 / LinkedIn 的 JobPosting 幾乎沒有 requirements 欄位（只有標題／摘要）。改從全文萃取後，
   這些台灣主要來源才不會對缺口分析「零貢獻」、導致缺口只反映 cake/yourator 的少量 tag。
2. cake / yourator 的 requirements 是 tag，常混入「Full-time / Remote / 台北」等非技能雜訊。
   只認詞庫內的技能名稱，這些雜訊自動被濾掉。

比對規則（皆大小寫不敏感）：
- 純英數別名 → 詞界比對（\b…\b），避免「ai」誤中 rail、「git」誤中 github。
- 含符號別名（c++ / node.js / ci/cd）→ 前後不接英數字的寬鬆邊界。
- 含中文別名 → 直接子字串（中文無詞界）。
"""
from __future__ import annotations

import re

# canonical 顯示名稱 -> 可比對別名（英文 + 中文）
LEXICON: dict[str, list[str]] = {
    # 程式語言
    "Python": ["python"],
    "JavaScript": ["javascript"],
    "TypeScript": ["typescript"],
    "Java": ["java"],
    "Go": ["golang", "go 語言"],
    "C++": ["c++"],
    "C#": ["c#"],
    "Rust": ["rust"],
    "SQL": ["sql"],
    "Scala": ["scala"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    # AI / ML
    "AI": ["ai", "artificial intelligence", "人工智慧", "人工智能"],
    "machine learning": ["machine learning", "機器學習", "ml"],
    "deep learning": ["deep learning", "深度學習"],
    "LLM": ["llm", "large language model", "大型語言模型", "大語言模型"],
    "NLP": ["nlp", "natural language processing", "自然語言處理"],
    "computer vision": ["computer vision", "電腦視覺"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented", "檢索增強"],
    "prompt engineering": ["prompt engineering", "提示工程"],
    "fine-tuning": ["fine-tuning", "fine tuning", "finetune", "微調"],
    "AI agent": ["ai agent", "agentic", "multi-agent", "multi agent", "智能體"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "Keras": ["keras"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "Hugging Face": ["hugging face", "huggingface"],
    "Transformer": ["transformer"],
    "LangChain": ["langchain"],
    "LangGraph": ["langgraph"],
    "OpenAI": ["openai"],
    "vector database": ["vector database", "vector db", "向量資料庫"],
    "embedding": ["embedding", "嵌入向量"],
    "MLOps": ["mlops"],
    "diffusion": ["diffusion model", "stable diffusion"],
    "reinforcement learning": ["reinforcement learning", "強化學習"],
    "recommendation system": ["recommendation system", "recommender", "推薦系統"],
    # 資料工程
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Spark": ["spark", "pyspark"],
    "Hadoop": ["hadoop"],
    "Kafka": ["kafka"],
    "Airflow": ["airflow"],
    "ETL": ["etl"],
    "data analysis": ["data analysis", "資料分析", "數據分析"],
    "data engineering": ["data engineering", "資料工程", "數據工程"],
    "BigQuery": ["bigquery"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    # 後端 / Web
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "React": ["react", "react.js"],
    "Vue": ["vue", "vue.js"],
    "Angular": ["angular"],
    "REST API": ["rest api", "restful"],
    "GraphQL": ["graphql"],
    "gRPC": ["grpc"],
    "Spring Boot": ["spring boot"],
    # 基礎設施 / 雲 / DevOps
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "GCP": ["gcp", "google cloud"],
    "Azure": ["azure"],
    "Terraform": ["terraform"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    "Linux": ["linux"],
    "Git": ["git"],
    "Redis": ["redis"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb"],
    "Elasticsearch": ["elasticsearch"],
    # 產品 / 專案
    "product management": ["product management", "產品管理"],
    "project management": ["project management", "專案管理"],
    "Agile": ["agile", "敏捷開發", "敏捷"],
    "Scrum": ["scrum"],
    "roadmap": ["product roadmap", "roadmap", "產品路線圖"],
    "user research": ["user research", "使用者研究", "用戶研究"],
    "requirements analysis": ["requirements analysis", "需求分析"],
    "stakeholder management": ["stakeholder management", "利害關係人管理"],
    # 設計
    "Figma": ["figma"],
    "UI/UX": ["ui/ux", "ui ux", "使用者介面", "使用者體驗", "用戶體驗"],
    "wireframing": ["wireframe", "wireframing", "線框圖"],
    "prototyping": ["prototype", "prototyping", "原型設計"],
    "design system": ["design system", "設計系統"],
    "Adobe Photoshop": ["photoshop"],
    "Adobe Illustrator": ["illustrator"],
    # 行銷 / 業務 / 客戶
    "SEO": ["seo", "搜尋引擎優化"],
    "SEM": ["sem", "搜尋引擎行銷"],
    "Google Analytics": ["google analytics", "ga4"],
    "content marketing": ["content marketing", "內容行銷"],
    "social media": ["social media", "社群經營", "社群行銷"],
    "advertising": ["廣告投放", "digital advertising", "數位廣告"],
    "CRM": ["crm", "客戶關係管理"],
    "B2B sales": ["b2b sales", "b2b 業務", "企業客戶開發"],
    "business development": ["business development", "商務開發", "業務開發"],
    "account management": ["account management", "客戶管理"],
    "customer success": ["customer success", "客戶成功"],
    "customer service": ["customer service", "customer support", "客戶服務", "客服"],
    # 營運 / 人資 / 財會 / 供應鏈
    "operations": ["operations management", "營運管理", "營運"],
    "process improvement": ["process improvement", "流程改善", "流程優化"],
    "recruiting": ["recruiting", "recruitment", "人才招募", "招募"],
    "payroll": ["payroll", "薪酬", "薪資作業"],
    "accounting": ["accounting", "會計"],
    "financial analysis": ["financial analysis", "財務分析"],
    "Excel": ["microsoft excel", "excel"],
    "ERP": ["erp", "企業資源規劃"],
    "procurement": ["procurement", "採購"],
    "supply chain": ["supply chain", "供應鏈"],
    "inventory management": ["inventory management", "庫存管理"],
    "logistics management": ["logistics management", "物流管理", "運輸管理"],
    "warehouse management": ["warehouse management", "倉儲管理", "倉庫管理"],
    "route planning": ["route planning", "路線規劃", "配送規劃"],
    "import/export": ["import export", "import/export", "進出口", "國際貿易", "報關"],
    # 行政 / 零售 / 餐旅
    "document management": ["document management", "文件管理", "檔案管理", "文書處理"],
    "data entry": ["data entry", "資料輸入", "資料建檔"],
    "scheduling": ["scheduling", "行程安排", "排程管理"],
    "POS": ["point of sale", "pos system", "pos 系統", "收銀系統"],
    "merchandising": ["merchandising", "商品陳列", "陳列管理"],
    "food safety": ["food safety", "食品安全", "食品衛生", "haccp"],
    "cooking": ["cooking", "烹飪", "烹調", "中餐烹調", "西餐烹調"],
    "coffee brewing": ["coffee brewing", "咖啡沖煮", "手沖咖啡", "義式咖啡"],
    "hotel operations": ["hotel operations", "旅館營運", "飯店營運", "旅宿服務"],
    "front desk": ["front desk", "櫃檯接待", "旅館櫃檯", "飯店櫃檯"],
    # 製造 / 工程 / 營建
    "production planning": ["production planning", "生產計畫", "生產排程", "產能規劃"],
    "quality control": ["quality control", "quality assurance", "品質管理", "品保", "品管"],
    "ISO 9001": ["iso 9001", "iso9001"],
    "lean manufacturing": ["lean manufacturing", "精實生產", "精實製造"],
    "equipment maintenance": ["equipment maintenance", "設備維護", "機台維修", "設備保養"],
    "CNC": ["cnc", "電腦數值控制"],
    "PLC": ["plc", "可程式邏輯控制器"],
    "AutoCAD": ["autocad", "auto cad"],
    "SolidWorks": ["solidworks", "solid works"],
    "PCB design": ["pcb design", "pcb layout", "電路板設計", "印刷電路板"],
    "semiconductor process": ["semiconductor process", "半導體製程", "晶圓製程"],
    "construction management": ["construction management", "工地管理", "營建管理"],
    "cost estimation": ["cost estimation", "工程估價", "成本估算"],
    "occupational safety": ["occupational safety", "職業安全", "職業安全衛生", "工安"],
    # 醫療 / 教育 / 法務 / 研究
    "patient care": ["patient care", "病患照護", "病人照護", "臨床照護"],
    "BLS": ["basic life support", "bls", "基本救命術"],
    "medication administration": ["medication administration", "給藥", "藥物管理"],
    "pharmacy practice": ["pharmacy practice", "藥事服務", "處方調劑", "藥品調劑"],
    "lesson planning": ["lesson planning", "教案設計", "課程設計", "備課"],
    "classroom management": ["classroom management", "班級經營", "班級管理"],
    "curriculum development": ["curriculum development", "課程發展", "教材設計"],
    "contract review": ["contract review", "合約審閱", "契約審查"],
    "legal research": ["legal research", "法律研究", "法規研究"],
    "compliance": ["regulatory compliance", "legal compliance", "法令遵循", "法遵"],
    "research methods": ["research methods", "研究方法", "研究設計"],
    "statistics": ["statistics", "統計分析", "統計學"],
    "SPSS": ["spss"],
    # 媒體 / 社福 / 金融 / 服務
    "copywriting": ["copywriting", "文案撰寫", "內容撰寫"],
    "video editing": ["video editing", "影片剪輯", "影音剪輯"],
    "Adobe Premiere": ["adobe premiere", "premiere pro"],
    "photography": ["photography", "攝影"],
    "translation": ["translation", "翻譯", "筆譯"],
    "interpretation": ["interpretation", "口譯"],
    "case management": ["case management", "個案管理"],
    "counseling": ["counseling", "諮商", "輔導"],
    "banking operations": ["banking operations", "銀行作業", "櫃員作業"],
    "wealth management": ["wealth management", "財富管理", "理財規劃"],
    "insurance planning": ["insurance planning", "保險規劃", "保單規劃"],
    "auditing": ["auditing", "audit", "審計", "稽核"],
    "taxation": ["taxation", "tax compliance", "稅務", "稅法"],
    "event planning": ["event planning", "活動企劃", "活動規劃"],
    "public relations": ["public relations", "媒體關係", "公關"],
    "security operations": ["security operations", "安全勤務", "保全勤務"],
    "cleaning operations": ["cleaning operations", "環境清潔", "清潔維護"],
    "hair styling": ["hair styling", "美髮", "髮型設計"],
    "beauty services": ["beauty services", "美容服務", "美容護理", "美甲"],
    # 語言與通用協作
    "English": ["business english", "英文", "英語"],
    "Japanese": ["business japanese", "日文", "日語"],
    "presentation": ["presentation skills", "簡報能力", "簡報製作"],
}


def _compile(alias: str):
    """把一個別名編成 (kind, matcher)：'sub' 子字串，'re' 已編譯正則。"""
    a = alias.lower()
    if not a.isascii():
        return ("sub", a)  # 中文等 → 子字串
    if a.replace(" ", "").isalnum():
        return ("re", re.compile(rf"\b{re.escape(a)}\b"))  # 純英數 → 詞界
    return ("re", re.compile(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])"))  # 含符號 → 寬鬆邊界


_COMPILED: list[tuple[str, list]] = [
    (canon, [_compile(a) for a in aliases]) for canon, aliases in LEXICON.items()
]


def _hit(matcher, text: str) -> bool:
    kind, m = matcher
    return (m in text) if kind == "sub" else (m.search(text) is not None)


def extract_skills(text: str) -> list[str]:
    """從一段文字萃取出詞庫內的 canonical 技能名稱（去重、保留詞庫順序）。"""
    t = (text or "").lower()
    return [canon for canon, ms in _COMPILED if any(_hit(m, t) for m in ms)]
