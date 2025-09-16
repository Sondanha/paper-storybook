# tests/gen_viz_results.py

import json
from pathlib import Path
import sys, os

# 루트(src) 경로 인식
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.llm.scene_splitter import split_into_scenes_with_narration
from src.services.llm.viz_classifier import classify_viz_batch

# 사용할 논문 ID (전처리 결과가 data/processed/{paper_id}/final_text.txt에 있어야 함)
paper_id = "out/ms"
base = Path(f"data/processed/{paper_id}")

# 1) 전처리 결과 읽기
with open(base / "final_text.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 2) Scene Splitter 실행 (JSON 파싱 보강 적용됨)
scenes = split_into_scenes_with_narration(text)

# scene_id 누락 대비: 자동 보정
for idx, s in enumerate(scenes):
    if "scene_id" not in s or not isinstance(s["scene_id"], int):
        s["scene_id"] = idx + 1

# 3) Viz Classifier 실행 (여기서만 LLM 호출 → 토큰 소모)
viz_results = classify_viz_batch(scenes)

# 4) 저장
out_path = Path(f"data/output/{paper_id}/viz_results.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(viz_results, f, ensure_ascii=False, indent=2)

print(f"Saved: {out_path}")
