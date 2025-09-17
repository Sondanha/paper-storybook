# tests/render_from_json.py

import json
from pathlib import Path
from src.services.visualization.diagram import render_scene_visualization
from src.services.visualization.dot_cleaner import clean_dot


def render_from_json(json_file: Path, out_dir: Path) -> None:
    """
    Render visualization images from an existing scene JSON file.

    Args:
        json_file (Path): Path to viz_*.json file
        out_dir (Path): Directory to save rendered images
    """
    with open(json_file, "r", encoding="utf-8") as f:
        scenes = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes:
        scene_id = scene.get("scene_id", "unknown")
        for viz in scene.get("visualizations", []):
            if viz.get("tool") != "graphviz":
                continue
            try:
                print(f"[Scene {scene_id}] Rendering {viz['viz_label']} ...")

                # 🔧 DOT 문자열 자동 클린업
                cleaned_prompt = clean_dot(viz["viz_prompt"])

                # 🐞 디버그 출력: 변환된 DOT 코드 확인
                print("---- DOT SOURCE (cleaned) ----")
                print(cleaned_prompt)
                print("-----------------------------")

                render_scene_visualization(
                    viz_prompt=cleaned_prompt,
                    scene_id=scene_id,
                    label=viz["viz_label"],
                    out_dir=out_dir,
                )
            except Exception as e:
                print(f"⚠️ Failed rendering scene {scene_id}: {e}")

    print(f"\n✅ Done. Check output dir: {out_dir.resolve()}")


if __name__ == "__main__":
    # data/viz_output 안에 있는 json 파일 중 하나 선택
    json_file = Path("data/viz_output/viz_ResNet.json")
    out_dir = Path("data/viz_output/rendered_ResNet")

    render_from_json(json_file, out_dir)
