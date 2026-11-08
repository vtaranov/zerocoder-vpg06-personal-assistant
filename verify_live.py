"""Real service checks; synthetic input, no Telegram sends. Private evidence only."""
import json
import time
from uuid import uuid4
from config import ROOT, load_config
from assistant import Assistant

def run():
    owner = "validation:" + uuid4().hex
    cfg = load_config()
    report = {"model": cfg.model, "owner": owner, "steps": [], "passed": False}
    a = None
    stage = "connect"
    try:
        a = Assistant(cfg)
        cases = [
            ("remember", "Запомни: моё учебное кодовое слово КЕДР-739.", None),
            ("recall_after_reconnect", "Какое моё учебное кодовое слово?", None),
            ("cat", "Вызови инструмент и расскажи случайный факт о кошках.", "cat_fact"),
            ("weather", "Вызови инструмент погоды и сообщи текущую погоду в Москве.", "weather"),
            ("dog", "Вызови инструмент: получи фото случайной собаки и проанализируй именно это изображение.", "analyze_dog"),
        ]
        for stage, text, expected_tool in cases:
            if stage == "recall_after_reconnect":
                a = Assistant(cfg)
            result = a.handle(owner, text)
            record = {"stage": stage, "input": text, "answer": result["answer"], "calls": result["calls"],
                      "results": result["tool_results"], "photos": len(result["attachments"])}
            # Weather is a ComponentTool: record its actual return message too.
            record["tool_messages"] = [m.to_dict() for m in result["messages"] if m.tool_call_results]
            report["steps"].append(record)
            assert result["answer"].strip()
            if expected_tool:
                assert expected_tool in [c["name"] for c in result["calls"]]
                if expected_tool != "weather":
                    assert any(c["name"] == expected_tool and c["result"]["ok"] for c in result["tool_results"])
                else:
                    assert any('"ok": true' in str(c.result).lower() or "'ok': True" in str(c.result) for m in result["messages"] for c in m.tool_call_results)
            if stage == "recall_after_reconnect":
                assert "КЕДР-739" in result["answer"]
            if stage == "dog":
                assert len(result["attachments"]) == 1 and len(result["attachments"][0]["bytes"]) > 1000
                (ROOT / "evidence" / "dog.jpg").write_bytes(result["attachments"][0]["bytes"])
            print(stage, "OK", flush=True)
        stage = "raw_memory_audit"
        rows = a.memory.rows(owner)
        report["memory_rows"] = rows
        texts = [s["input"] for s in report["steps"]]
        assert len(rows) == len(texts)
        assert sorted(r["metadata"]["content"] for r in rows) == sorted(texts)
        assert all(set(r["metadata"]) <= {"content", "type", "created_at"} for r in rows)
        assert a.memory.search(owner + ":other", "кодовое слово") == []
        report["checks"] = {"raw_user_messages_only": True, "owner_isolation": True, "reconnect_recall": True}
        report["passed"] = True
    except Exception as exc:
        report["error"] = {"stage": stage, "type": type(exc).__name__}
        print(stage, type(exc).__name__, flush=True)
    finally:
        if a:
            try:
                a.memory.clear(owner)
                report["test_namespace_cleaned"] = True
            except Exception as exc:
                report["cleanup_error"] = type(exc).__name__
                report["passed"] = False
        out = ROOT / "evidence" / ("live-" + time.strftime("%Y%m%dT%H%M%S") + ".json")
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print("EVIDENCE", out.name, "passed", report["passed"], flush=True)
    return report["passed"]
if __name__ == "__main__":
    (ROOT / "evidence").mkdir(exist_ok=True)
    raise SystemExit(0 if run() else 1)
