# tests/pipeline_test.py

from src.services.llm.scene_splitter import split_into_scenes_with_narration

if __name__ == "__main__":
    # 전처리 결과를 가정한 긴 문자열 (실제론 preprocess 모듈에서 반환)
    dummy_text = r"""
    \begin{abstract}
    The dominant sequence transduction models are based on complex recurrent or convolutional
    neural networks that include an encoder and a decoder. The best performing models also connect
    the encoder and decoder through an attention mechanism. We propose a new simple network
    architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence
    and convolutions entirely.
    \end{abstract}

    \section{Introduction}
    Recurrent neural networks, long short-term memory [CITATION] and gated recurrent [CITATION]
    neural networks in particular, have been firmly established as state of the art approaches in
    sequence modeling and transduction problems such as language modeling and machine translation.
    """

    scenes = split_into_scenes_with_narration(dummy_text)

    print("=== Scene Split + Narration Result ===")
    for s in scenes:
        print(f"[Scene {s.get('scene_id')}] {s.get('title')}")
        print(f"Narration: {s.get('narration')[:150]}...")
        print("-" * 40)
