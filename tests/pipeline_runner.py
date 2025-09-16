#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
전처리 파이프라인 테스트 실행기
- 논문 TeX 소스 루트를 지정하면 merged_body.tex 생성
"""

from pathlib import Path
from src.texprep.pipeline import run_pipeline


def main():
    # 테스트용 config
    cfg = {
        "root_dir": "data/processed/1706.03762/source",  # ← 논문 TeX 소스 루트 경로로 바꿔
        "out_dir": "data/processed/out",                 # ← 산출물 저장 폴더
        "select": {"mode": "auto_merge"},                # or "expand"
    }

    try:
        result = run_pipeline(cfg)
        print("\n=== 파이프라인 실행 결과 ===")
        for k, v in result.items():
            print(f"{k}: {v}")
    except Exception as e:
        print("❌ 오류:", e)


if __name__ == "__main__":
    main()

# venv 활성화한 상태에서
# python -m tests.pipeline_runner
