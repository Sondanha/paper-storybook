# tests\run_scene_splitter.py

import json
from pathlib import Path

from src.services.llm.scene_splitter import split_into_scenes_with_narration

if __name__ == "__main__":
    # 입력 파일 읽기
    text_path = Path("data/processed/out/ms/final_text.txt")
    with open(text_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Scene Splitter 실행 (리턴 타입: list[dict] 또는 str)
    scenes = split_into_scenes_with_narration(full_text)

    # 출력 디렉토리 준비
    out_dir = Path("data/output/out/ms")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 결과 저장 경로
    out_file = out_dir / "scene_split_result.json"

    # 파일 저장: JSON으로 직렬화 (escape 안전하게 처리)
    if isinstance(scenes, list):
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(scenes, f, ensure_ascii=False, indent=2)
        print(f"[SceneSplitter] JSON 결과 저장 완료: {out_file}")
    else:
        # 만약 파싱 실패 시 문자열 그대로 저장
        out_file = out_dir / "scene_split_raw.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(scenes)
        print(f"[SceneSplitter] RAW 응답 저장 완료: {out_file}")
