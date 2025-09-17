import re
import itertools

_dummy_counter = itertools.count(1)

def clean_dot(dot_source: str) -> str:
    cleaned = dot_source

    # 1) 배열 형태 풀기
    pattern = re.compile(r'(\w+)\s*->\s*\[([^\]]+)\]\s*;?')
    def expand_edges(match):
        src = match.group(1)
        targets = [t.strip().strip('"') for t in match.group(2).split(",")]
        edges = [f'{src} -> "{t}";' for t in targets if t]
        return " ".join(edges)
    cleaned = pattern.sub(expand_edges, cleaned)

    # 2) 잘못된 "label="..."" 패턴 보정
    label_pattern = re.compile(r'(\w+)\s*->\s*"label="([^"]+)"')
    cleaned = label_pattern.sub(
        lambda m: f'{m.group(1)} -> DummyNode{next(_dummy_counter)} [label="{m.group(2)}"];',
        cleaned,
    )

    # 3) 목적지 노드 없이 [label=...]만 있는 경우
    orphan_label_pattern = re.compile(r'->\s*\[label="([^"]+)"\]')
    cleaned = orphan_label_pattern.sub(
        lambda m: f'-> DummyNode{next(_dummy_counter)} [label="{m.group(1)}"]',
        cleaned,
    )

    # 4) inline label 붙은 경우 처리: NodeLabel="..." → Node [label="..."]
    inline_label_pattern = re.compile(r'(\w+)(label="[^"]+")')
    cleaned = inline_label_pattern.sub(r'\1 [\2]', cleaned)

    # 5) 세미콜론 자동 보정 (edge 사이에 세미콜론 없으면 추가)
    cleaned = re.sub(r'"\]\s+(\w+)', r'"];\n\1', cleaned)

    # 6) 중복 세미콜론 정리
    cleaned = re.sub(r';{2,}', ';', cleaned)

    return cleaned
