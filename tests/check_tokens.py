# tests/check_tokens.py

import tiktoken
from pathlib import Path

def count_tokens(file_path: Path):
    enc = tiktoken.get_encoding("cl100k_base")
    text = file_path.read_text(encoding="utf-8")
    return len(enc.encode(text))


if __name__ == "__main__":
    base_dir = Path("data/processed")
    txt_files = list(base_dir.rglob("*.txt"))

    if not txt_files:
        print(f"[Error] {base_dir} 안에 .txt 파일이 없습니다")
    else:
        for f in txt_files:
            try:
                token_count = count_tokens(f)
                print(f"[Token Count] {f}: {token_count} tokens")
            except Exception as e:
                print(f"[Error] {f}: {e}")

# 실행 예시:
# (.venv) python -m tests.check_tokens

# [Token Count] data\processed\BERT.txt: 12934 tokens
# [Token Count] data\processed\DCGAN.txt: 4892 tokens
# [Token Count] data\processed\LLaMA.txt: 13278 tokens
# [Token Count] data\processed\LoRA.txt: 14641 tokens
# [Token Count] data\processed\ResNet.txt: 15052 tokens
# [Token Count] data\processed\Transformer.txt: 10084 tokens
# [Token Count] data\processed\VGGNet.txt: 9916 tokens
# [Token Count] data\processed\YOLOv1.txt: 10506 tokens