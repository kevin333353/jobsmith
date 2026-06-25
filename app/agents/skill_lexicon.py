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
