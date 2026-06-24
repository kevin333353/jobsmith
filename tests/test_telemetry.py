from app import telemetry


def test_record_and_drain_aggregates():
    telemetry.start_run()
    m = telemetry.marker()
    telemetry.record_llm(input_tokens=100, output_tokens=50, cost_usd=0.001)
    telemetry.record_llm(input_tokens=20, output_tokens=10, cost_usd=0.0005)
    d = telemetry.drain_since(m)
    assert d["calls"] == 2
    assert d["input_tokens"] == 120
    assert d["output_tokens"] == 60
    assert abs(d["cost_usd"] - 0.0015) < 1e-9


def test_marker_isolates_per_node():
    telemetry.start_run()
    telemetry.record_llm(input_tokens=5, output_tokens=5)   # 前一節點
    m = telemetry.marker()
    telemetry.record_llm(input_tokens=10, output_tokens=20, cost_usd=0.002)  # 本節點
    d = telemetry.drain_since(m)
    assert d["calls"] == 1
    assert d["input_tokens"] == 10 and d["output_tokens"] == 20


def test_record_llm_without_run_is_noop():
    # 沒有作用中的蒐集器時不應丟例外（後端在非 graph 情境也可能呼叫）
    telemetry.start_run()
    telemetry.drain_since(0)  # 確認可呼叫
    telemetry.record_llm(input_tokens=1)  # 不丟例外即通過


def test_record_usage_parses_claude_envelope():
    import app.llm_cli as cli
    telemetry.start_run()
    m = telemetry.marker()
    cli._record_usage({
        "usage": {"input_tokens": 30, "cache_read_input_tokens": 10,
                  "cache_creation_input_tokens": 5, "output_tokens": 40},
        "total_cost_usd": 0.012,
    })
    d = telemetry.drain_since(m)
    assert d["input_tokens"] == 45      # 30 + 10 + 5
    assert d["output_tokens"] == 40
    assert abs(d["cost_usd"] - 0.012) < 1e-9
