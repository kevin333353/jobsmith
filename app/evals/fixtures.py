"""Golden 評測案例：(jd_text, profile) 配對，供 eval harness 量測反思迴圈成效。"""
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
]
