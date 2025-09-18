# tests/run_viz_pipeline.py

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.services.llm.scene_splitter import split_into_scenes_with_narration
from src.services.llm.viz_classifier import classify_scenes_iteratively


def _print_header(msg: str) -> None:
    print(f"\n[Pipeline] ===== {msg} =====")


def _debug_peek(text: str, n: int = 200) -> str:
    # 줄바꿈 가시화
    return text[:n].replace("\r", "\\r").replace("\n", "⏎")


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def _summarize_vizzes(v: dict) -> str:
    vt = [vv.get("viz_type") for vv in v.get("visualizations", [])]
    return f"viz_types={vt}"


def run_once(paper_name: str, out_dir: Path, max_scenes: int | None, debug: bool) -> None:
    start_total = time.perf_counter()

    text_path = Path(f"data/processed/{paper_name}.txt")
    if not text_path.exists():
        print(f"[Pipeline][ERROR] 입력 파일 없음: {text_path}")
        return

    full_text = _load_text(text_path)
    if debug:
        print(f"[Debug] input chars={len(full_text):,}")
        print(f"[Debug] first 200 chars:\n{_debug_peek(full_text, 200)}")

    # 1) Scene Split
    _print_header("STEP 1: Scene Splitter 실행")
    t0 = time.perf_counter()
    scenes = split_into_scenes_with_narration(full_text)
    dt_split = time.perf_counter() - t0

    if not isinstance(scenes, list) or len(scenes) == 0:
        print("[Pipeline][ERROR] Scene Splitter 결과가 유효하지 않음")
        return

    if debug:
        print(f"[Debug] scenes count={len(scenes)} ids={[s.get('scene_id') for s in scenes]}")
        _save_json(out_dir / f"_debug_scenes_{paper_name}.json", scenes)

    # 최소 장면 수 확인 및 강제 중단 옵션
    if len(scenes) < 2:
        print(f"[Pipeline][WARN] Scene Splitter가 {len(scenes)}개만 반환. 입력 혹은 분할 로직 점검 필요.")
        # 디버깅을 돕기 위해 원본 텍스트 저장
        (out_dir / "_debug").mkdir(parents=True, exist_ok=True)
        with (out_dir / "_debug" / f"_debug_fulltext_{paper_name}.txt").open("w", encoding="utf-8") as f:
            f.write(full_text)

    # 테스트 시간 보호: 필요 시 앞쪽 N개만
    if isinstance(max_scenes, int) and max_scenes > 0:
        scenes = scenes[:max_scenes]
        print(f"[Pipeline] ⏱ max_scenes={max_scenes} 적용 → 실제 처리 {len(scenes)}개")

    # 2) Viz Classifier
    _print_header("STEP 2: Viz Classifier 반복 호출")
    t1 = time.perf_counter()
    viz_results = classify_scenes_iteratively(scenes)
    dt_viz = time.perf_counter() - t1

    # 요약 출력
    print(f"[Pipeline] Viz Classifier 결과 개수: {len(viz_results)}")
    for v in viz_results:
        sid = v.get("scene_id")
        title = v.get("title")
        if "error" in v:
            print(f"  - Scene {sid}: ERROR → {v['error']}")
        else:
            print(f"  - Scene {sid}: {title} | {_summarize_vizzes(v)}")

    # 저장
    viz_file = out_dir / f"viz_{paper_name}.json"
    _save_json(viz_file, viz_results)
    print(f"[Pipeline] 최종 viz 결과 저장 완료: {viz_file}")

    # 시간 요약
    dt_total = time.perf_counter() - start_total
    print(
        f"[Pipeline] 시간 요약: split={dt_split:.2f}s, "
        f"viz={dt_viz:.2f}s, total={dt_total:.2f}s"
    )


def parse_papers(arg: str | None) -> Iterable[str]:
    if not arg:
        # 기본 단일 실행. 필요하면 여기서 기본 세트 바꿔라.
        return ["ResNet"]
    # 쉼표/공백 분리 허용
    parts = [p.strip() for p in arg.replace(",", " ").split() if p.strip()]
    return parts or ["ResNet"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run visualization pipeline for AI papers.")
    parser.add_argument(
        "--papers",
        type=str,
        default=None,
        help="공백 또는 콤마로 구분된 논문 이름들 (예: 'Transformer YOLOv1' 또는 'Transformer,YOLOv1')",
    )
    parser.add_argument(
        "--max-scenes",
        type=int,
        default=None,
        help="처리할 최대 씬 개수 제한(앞에서부터). 생략하면 전체 처리.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="디버그 로그 및 중간 산출물 저장",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("data/viz_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    papers = list(parse_papers(args.papers))
    print(f"[Pipeline] 대상 논문: {papers}")

    for paper_name in papers:
        _print_header(f"{paper_name} 처리 시작 ({timestamp})")
        try:
            run_once(
                paper_name=paper_name,
                out_dir=out_dir,
                max_scenes=args.max_scenes,
                debug=args.debug,
            )
        except KeyboardInterrupt:
            print("\n[Pipeline] 사용자가 중단함.")
            sys.exit(130)
        except Exception as e:
            print(f"[Pipeline][ERROR] {paper_name} 처리 중 예외: {e}")

    print("\n[Pipeline] 모든 작업 종료.")


if __name__ == "__main__":
    main()

# python -m tests.run_viz_pipeline --papers "LLaMA DCGAN Transformer YOLOv1" --max-scenes 5
