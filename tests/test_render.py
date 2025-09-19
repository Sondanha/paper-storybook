# tests/test_render.py  (Python 3.11+)
import json
import sys
import traceback
from pathlib import Path

# ── 패키지/경로 안전장치 ─────────────────────────────────────────────
THIS_FILE = Path(__file__).resolve()
ROOT = THIS_FILE.parents[1]           # project root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))     # src/ 패키지 임포트 보장

from src.services.visualization.dot_cleaner import clean_viz_entry
from src.services.visualization.diagram import render_diagram
from src.services.compositor.scene_composer import compose_scene
from src.services.compositor.pdf_exporter import export_pdf   # ⭐ PDF 내보내기 추가


def log(*args):
    print(*args, flush=True)


def main():
    # 실행 환경 로그
    log("▶ script:", THIS_FILE)
    log("▶ root  :", ROOT)
    log("▶ cwd   :", Path.cwd())

    if len(sys.argv) < 2:
        log("Usage: python -m tests.test_render <PAPER_NAME>")
        log("Example: python -m tests.test_render BERT")
        # 발견 가능한 JSON 힌트
        viz_dir = ROOT / "data" / "viz_json_ko"
        if viz_dir.exists():
            samples = sorted(p.name for p in viz_dir.glob("viz_*.json"))
            if samples:
                log("Found JSONs:", ", ".join(samples[:10]), "...")
        sys.exit(1)

    paper = sys.argv[1]
    data_path = ROOT / "data" / "viz_json_ko" / f"viz_{paper}.json"
    out_dir = ROOT / "data" / "viz_jpg" / paper
    scene_out_dir = ROOT / "data" / "scenes" / paper
    font_path = ROOT / "assets" / "NanumGothic.ttf"

    # 입력 검증
    if not data_path.exists():
        log(f"❌ 파일 없음: {data_path}")
        sys.exit(1)

    # 폰트 존재 여부 안내(실패는 아님)
    if not font_path.exists():
        log(f"⚠️ 폰트 없음(한글 깨질 수 있음): {font_path}")

    # 출력 디렉토리 준비
    out_dir.mkdir(parents=True, exist_ok=True)
    scene_out_dir.mkdir(parents=True, exist_ok=True)

    # JSON 로드
    try:
        with data_path.open("r", encoding="utf-8") as f:
            scenes = json.load(f)
    except Exception:
        log("❌ JSON 파싱 실패:", data_path)
        traceback.print_exc()
        sys.exit(1)

    if not isinstance(scenes, list) or not scenes:
        log("❌ scenes 리스트가 비었거나 형식이 잘못됨:", type(scenes))
        sys.exit(1)

    log(f"✅ 로드 완료: {data_path} (scenes={len(scenes)})")

    ok, fail = 0, 0
    scene_files = []   # ⭐ 합성된 씬 PNG 경로 모아두기

    for idx, scene in enumerate(scenes, start=1):
        sid = scene.get("scene_id", f"idx{idx}")
        try:
            # 1) DOT 보정
            cleaned = clean_viz_entry(scene)
            dot_code = cleaned.get("diagram", 'digraph G { dummy [label="auto_fallback"]; }')

            # 2) 다이어그램 생성
            diagram_png = render_diagram(dot_code, out_dir, sid)
            log(f"🖼  diagram  scene={sid} → {diagram_png}")

            # 3) 나레이션 추출
            narration = scene.get("narration", "")

            # 4) 합성 씬 생성
            scene_png = scene_out_dir / f"scene_{sid}.png"
            compose_scene(
                diagram_png,
                narration,
                scene_png,
                # font_path=font_path,  # 필요시 주석 해제
            )
            if scene_png.exists() and scene_png.stat().st_size > 0:
                ok += 1
                scene_files.append(scene_png)   # ⭐ PDF 합치기 위해 추가
                log(f"🎬 final    scene={sid} → {scene_png}")
            else:
                fail += 1
                log(f"❌ 저장 실패(파일 없음/0바이트): {scene_png}")

        except Exception:
            fail += 1
            log(f"💥 예외 발생: scene={sid}")
            traceback.print_exc()

    # ⭐ PDF 합치기
    if scene_files:
        pdf_out = scene_out_dir / f"{paper}.pdf"
        export_pdf(scene_files, pdf_out)
        log(f"📕 PDF saved: {pdf_out}")

    log(f"끝. 성공 {ok} / 실패 {fail} / 총 {len(scenes)}")


if __name__ == "__main__":
    main()
