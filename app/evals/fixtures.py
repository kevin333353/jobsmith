"""Golden 評測案例：(jd_text, profile) 配對，供一次性投遞包品管 harness 使用。"""
from app.models import Profile

GOLDEN: list[dict] = [
    {
        "name": "llm_app_engineer",
        "jd_text": (
            "LLM 應用工程師\n公司：智核科技\n地點：台北市\n"
            "需求：3 年以上後端經驗、熟 Python 與 FastAPI、做過 RAG / Agent 系統、"
            "熟向量資料庫與 prompt engineering；加分：LangGraph、評估與 A/B 測試。"
        ),
        "profile": Profile(
            name="陳小安", summary="三年 Python 後端，近一年專注 LLM 與 RAG 應用",
            skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LangChain", "RAG"],
            experiences=["用 FastAPI 開發訂單 API，QPS 提升 3 倍",
                         "自建 RAG 客服機器人，工單下降 25%"],
            education="資工系學士", years_experience=3,
            preferred_roles=["AI 工程師", "LLM 應用工程師"],
            raw_text="陳小安｜Python 後端 / LLM 應用工程師。三年後端，近一年 LLM/RAG。"),
    },
    {
        "name": "ml_engineer_nlp",
        "jd_text": (
            "機器學習工程師（NLP）\n公司：語析資料\n地點：台北市（遠端友善）\n"
            "需求：熟 PyTorch 與 Transformers、微調與部署 NLP/LLM 模型、建立資料管線；"
            "加分：MLOps、線上推論服務、Docker/K8s。"
        ),
        "profile": Profile(
            name="林大為", summary="兩年資料科學家，做過 NLP 模型微調與部署",
            skills=["Python", "PyTorch", "Transformers", "NLP", "Docker"],
            experiences=["微調 BERT 做客訴分類，F1 0.91",
                         "建置每日批次推論管線，處理百萬級文本"],
            education="資料科學碩士", years_experience=2,
            preferred_roles=["機器學習工程師", "NLP 工程師"],
            raw_text="林大為｜資料科學家。NLP 模型微調與部署兩年。"),
    },
    {
        "name": "agent_engineer",
        "jd_text": (
            "AI Agent 工程師\n公司：未來智能\n地點：新竹市\n"
            "需求：熟 LangGraph 多 agent 編排、工具呼叫與評估、Python/FastAPI、"
            "能把 agent 系統落地上線；加分：observability、cost/latency 調校。"
        ),
        "profile": Profile(
            name="王宇婷", summary="後端轉 AI agent 工程，做過 multi-agent POC",
            skills=["Python", "FastAPI", "LangGraph", "Multi-agent", "評估"],
            experiences=["以 LangGraph 打造投遞包多 agent 系統（supervisor + 反思迴圈）",
                         "加上 token/成本 telemetry 與 golden-set 評測"],
            education="資工系學士", years_experience=3,
            preferred_roles=["AI Agent 工程師", "LLM 應用工程師"],
            raw_text="王宇婷｜AI agent 工程。LangGraph 多 agent + 評測。"),
    },
    {
        "name": "data_engineer_ml",
        "jd_text": (
            "資料工程師（ML 平台）\n公司：洞數據\n地點：台北市\n"
            "需求：熟 Python 與 SQL、建置 ETL 與資料管線、Spark/Airflow、雲端（GCP/AWS）；"
            "加分：支援 ML 特徵管線、BigQuery、資料品質監控。"
        ),
        "profile": Profile(
            name="周建宏", summary="三年資料工程，建過批次與串流資料管線",
            skills=["Python", "SQL", "Airflow", "Spark", "GCP", "BigQuery"],
            experiences=["以 Airflow 排程每日 ETL，支撐 BI 與報表",
                         "建置 Spark 串流管線處理事件資料"],
            education="資工系學士", years_experience=3,
            preferred_roles=["資料工程師", "ML 平台工程師"],
            raw_text="周建宏｜資料工程師。ETL/Spark/Airflow 三年。"),
    },
    {
        "name": "senior_llm_platform",
        "jd_text": (
            "資深 LLM 平台工程師\n公司：智匯雲\n地點：台北市（遠端友善）\n"
            "需求：5 年以上後端、設計 LLM 推論服務與 RAG 平台、熟 Python/FastAPI 與 Kubernetes、"
            "成本與延遲優化、可觀測性；加分：vector database、multi-agent、評估框架。"
        ),
        "profile": Profile(
            name="許雅婷", summary="六年後端，近兩年帶 LLM 平台與 RAG 服務上線",
            skills=["Python", "FastAPI", "Kubernetes", "RAG", "vector database", "MLOps"],
            experiences=["設計多租戶 LLM 推論閘道，p95 延遲降 40%",
                         "建置 RAG 平台與離線評估，導入成本/延遲儀表板"],
            education="資工碩士", years_experience=6,
            preferred_roles=["資深 LLM 工程師", "LLM 平台工程師"],
            raw_text="許雅婷｜資深後端 / LLM 平台。RAG 服務與評估兩年。"),
    },
]
