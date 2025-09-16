import pytest
import json
from unittest.mock import patch

from src.services.llm import viz_classifier

# 샘플 scene
SCENE = {
    "scene_id": 1,
    "title": "Transformer 소개",
    "narration": "RNN의 한계를 극복하기 위해 Transformer 구조를 제안했다.",
    "raw_text": "Attention is all you need ..."
}

def test_build_prompt_contains_schema():
    prompt = viz_classifier._build_prompt(SCENE, rules=None, prefer_tool="graphviz")
    assert "viz_type" in prompt
    assert "graphviz" in prompt
    assert "JSON 스키마" in prompt  # ← 포함되는 게 맞음

def test_sanitize_and_complete_defaults():
    raw = {
        "scene_id": 1,
        "viz_type": "nonsense",
        "tool": "unknown",
        "viz_prompt": "```digraph G {A->B}```"
    }
    out = viz_classifier._sanitize_and_complete(raw, prefer_tool="graphviz")
    assert out["viz_type"] == "diagram"
    assert out["tool"] in {"graphviz", "mermaid"}
    assert "`" not in out["viz_prompt"]

@patch("src.services.llm.viz_classifier.call_claude")
def test_classify_viz_valid_json(mock_call):
    fake_json = json.dumps({
        "scene_id": 1,
        "viz_type": "illustration",
        "viz_label": "conceptual_illustration",
        "tool": "stability",
        "viz_prompt": "Transformer를 설명하는 삽화",
        "meta": {"language": "ko"}
    })
    mock_call.return_value = fake_json

    result = viz_classifier.classify_viz(SCENE)
    assert result["viz_type"] == "illustration"
    assert "Transformer" in result["viz_prompt"]

@patch("src.services.llm.viz_classifier.call_claude")
def test_classify_viz_fallback_on_parse_error(mock_call):
    mock_call.return_value = "nonsense not json"

    result = viz_classifier.classify_viz(SCENE)
    assert result["viz_type"] == "diagram"
    assert "digraph" in result["viz_prompt"]

@patch("src.services.llm.viz_classifier.classify_viz")
def test_classify_viz_batch_continues_on_error(mock_classify):
    # 첫 scene은 정상, 두번째는 예외 발생
    mock_classify.side_effect = [
        {"scene_id": 1, "viz_type": "diagram", "tool": "graphviz", "viz_prompt": "ok", "meta": {}},
        Exception("LLM error")
    ]
    scenes = [SCENE, {"scene_id": 2, "title": "에러씬", "narration": "실패"}]
    results = viz_classifier.classify_viz_batch(scenes)
    assert len(results) == 2
    assert results[1]["viz_type"] == "diagram"  # fallback
    assert "viz error" in results[1]["viz_prompt"]
