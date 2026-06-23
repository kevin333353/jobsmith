"""集中管理環境變數與模型分層。"""
from dotenv import load_dotenv

load_dotenv()  # 從 .env 載入 ANTHROPIC_API_KEY 等

# 模型分層：依任務難度選模型，集中於此便於切換與成本控制。
MODEL_TIERS: dict[str, str] = {
    "cheap": "claude-haiku-4-5-20251001",   # 單純抽取（解析）
    "standard": "claude-sonnet-4-6",        # 匹配/生成主力
    "deep": "claude-opus-4-8",              # Critic/Supervisor 硬判斷
}


def get_model(tier: str) -> str:
    """取得某分層對應的 model id；未知分層丟 KeyError。"""
    return MODEL_TIERS[tier]
