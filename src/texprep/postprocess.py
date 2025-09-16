import re
from pathlib import Path

def replace_citations(text: str) -> str:
    """모든 \cite{...}, \citep{...}, \citet{...} → [CITATION]"""
    return re.sub(r"\\cite[t|p]?\{[^}]+\}", "[CITATION]", text)

def inline_equations(text: str) -> str:
    """블록 수식/인라인 수식 → 텍스트"""
    text = re.sub(r"\$\$(.*?)\$\$", r"\1", text, flags=re.S)
    text = re.sub(r"\$(.*?)\$", r"\1", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text, flags=re.S)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text, flags=re.S)
    return text

def extract_captions(text: str) -> str:
    """figure/table 환경 제거, caption만 보존"""
    def repl(match):
        block = match.group(0)
        # 캡션 추출
        m = re.search(r"\\caption\{([^}]*)\}", block, re.S)
        if not m:
            return ""  # 캡션 없으면 삭제
        caption = m.group(1).strip()
        if match.group(1) == "figure":
            return f"[FIGURE] {caption}\n"
        else:
            return f"[TABLE] {caption}\n"

    return re.sub(r"\\begin\{(figure|table)\}.*?\\end\{\1\}", repl, text, flags=re.S)

def run_postprocess(input_path: str, output_path: str):
    text = Path(input_path).read_text(encoding="utf-8")

    text = replace_citations(text)
    text = inline_equations(text)
    text = extract_captions(text)

    Path(output_path).write_text(text, encoding="utf-8")
    return output_path
