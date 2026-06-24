import contextvars
from concurrent.futures import ThreadPoolExecutor

from app import telemetry


def test_begin_end_node_aggregates():
    tok = telemetry.begin_node()
    telemetry.record_llm(input_tokens=100, output_tokens=50, cost_usd=0.001)
    telemetry.record_llm(input_tokens=20, output_tokens=10, cost_usd=0.0005)
    usage = telemetry.end_node(tok)
    assert usage["calls"] == 2
    assert usage["input_tokens"] == 120
    assert usage["output_tokens"] == 60
    assert abs(usage["cost_usd"] - 0.0015) < 1e-9


def test_record_without_active_node_is_noop():
    # 不在任何節點蒐集區間（sink=None）→ record 不丟例外、被丟棄
    telemetry.record_llm(input_tokens=1)


def test_record_usage_parses_claude_envelope():
    import app.llm_cli as cli
    tok = telemetry.begin_node()
    cli._record_usage({
        "usage": {"input_tokens": 30, "cache_read_input_tokens": 10,
                  "cache_creation_input_tokens": 5, "output_tokens": 40},
        "total_cost_usd": 0.012,
    })
    usage = telemetry.end_node(tok)
    assert usage["input_tokens"] == 45      # 30 + 10 + 5
    assert usage["output_tokens"] == 40
    assert abs(usage["cost_usd"] - 0.012) < 1e-9


def test_parallel_nodes_do_not_cross_count():
    # 平行生成節點各自 copy_context → 各自蒐集器，彼此不互相灌 token（修 fan-out 交叉計數）
    results = {}

    def worker(name, n):
        def run():
            tok = telemetry.begin_node()
            for _ in range(n):
                telemetry.record_llm(input_tokens=10, output_tokens=5, cost_usd=0.001)
            results[name] = telemetry.end_node(tok)
        contextvars.copy_context().run(run)

    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in [ex.submit(worker, "a", 1), ex.submit(worker, "b", 2), ex.submit(worker, "c", 3)]:
            f.result()

    assert results["a"]["calls"] == 1
    assert results["b"]["calls"] == 2
    assert results["c"]["calls"] == 3       # 各自獨立，無交叉計數
    assert results["c"]["input_tokens"] == 30
