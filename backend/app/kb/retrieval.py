"""Lexical retrieval over `kb_chunks`: BM25 with light Russian suffix stripping.

Deliberately dependency-free: the prototype must run offline without an embedding
service, and PLAN §5 names BM25 as the offline fallback. Tokenization lowercases,
splits on word characters and strips one common Russian ending so «отгул»,
«отгула» and «отгуле» meet. This is not a morphological analyzer — it is a
predictable approximation with tests on the questions we actually answer.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)

MIN_WORD_LENGTH = 3

# Longest first: strip exactly one ending, and only when a 4-character stem remains.
_SUFFIXES = tuple(
    sorted(
        {
            "ами",
            "ями",
            "ого",
            "его",
            "ому",
            "ему",
            "ыми",
            "ими",
            "ых",
            "их",
            "ая",
            "яя",
            "ое",
            "ее",
            "ые",
            "ие",
            "ов",
            "ев",
            "ей",
            "ой",
            "ый",
            "ий",
            "ам",
            "ям",
            "ах",
            "ях",
            "ом",
            "ем",
            "ую",
            "юю",
            "а",
            "я",
            "о",
            "е",
            "у",
            "ю",
            "ы",
            "и",
            "ь",
            "й",
        },
        key=len,
        reverse=True,
    )
)

STOP_WORDS = frozenset(
    {
        "а",
        "без",
        "бы",
        "был",
        "была",
        "были",
        "было",
        "быть",
        "в",
        "вам",
        "ваш",
        "ваша",
        "ваши",
        "все",
        "всё",
        "весь",
        "вы",
        "где",
        "да",
        "для",
        "до",
        "его",
        "ее",
        "её",
        "ей",
        "если",
        "есть",
        "ещё",
        "еще",
        "же",
        "за",
        "зачем",
        "здесь",
        "и",
        "из",
        "или",
        "им",
        "их",
        "к",
        "как",
        "какая",
        "какие",
        "каких",
        "какой",
        "ко",
        "когда",
        "кто",
        "кому",
        "куда",
        "ли",
        "мне",
        "меня",
        "можно",
        "мой",
        "моя",
        "мои",
        "мы",
        "на",
        "надо",
        "нам",
        "нас",
        "не",
        "него",
        "нее",
        "нет",
        "ни",
        "но",
        "нужно",
        "о",
        "об",
        "он",
        "она",
        "они",
        "оно",
        "от",
        "откуда",
        "очень",
        "по",
        "под",
        "пожалуйста",
        "при",
        "про",
        "потом",
        "почему",
        "разве",
        "расскажи",
        "с",
        "самый",
        "свой",
        "себе",
        "сейчас",
        "со",
        "так",
        "также",
        "там",
        "такое",
        "теперь",
        "то",
        "тогда",
        "только",
        "тот",
        "тут",
        "ты",
        "у",
        "уже",
        "чего",
        "чей",
        "чем",
        "через",
        "что",
        "чтобы",
        "эта",
        "эти",
        "это",
        "этот",
        "я",
    }
)

K1 = 1.5
B = 0.75
MIN_SCORE = 1.0
RELATIVE_CUTOFF = 0.3


class TextChunk(Protocol):
    """Anything with `content` — `KbChunk` rows and test doubles both qualify."""

    content: str


def stem(word: str) -> str:
    """Strip one common Russian ending (light, reversible, no dictionary needed)."""
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase words → stems, minus stop words and one/two-letter noise."""
    return [
        stem(word)
        for word in _WORD_RE.findall(text.lower())
        if len(word) >= MIN_WORD_LENGTH and word not in STOP_WORDS
    ]


def rank_chunks(
    query: str,
    chunks: Sequence[TextChunk],
    *,
    limit: int = 3,
    min_score: float = MIN_SCORE,
    relative_cutoff: float = RELATIVE_CUTOFF,
) -> list[tuple[TextChunk, float]]:
    """BM25 ranking; returns `(chunk, score)` pairs above an absolute+relative cutoff.

    A query needs at least one matched term (two for a long query) and the score
    must clear `min_score` — that is what makes an unrelated question return an
    empty list instead of the least-bad document.
    """
    query_terms = list(dict.fromkeys(tokenize(query)))
    if not query_terms or not chunks:
        return []

    term_counts = [Counter(tokenize(chunk.content)) for chunk in chunks]
    lengths = [sum(counter.values()) for counter in term_counts]
    total = len(term_counts)
    average_length = (sum(lengths) / total) or 1.0

    document_frequency: Counter[str] = Counter()
    for counter in term_counts:
        document_frequency.update(counter.keys())

    required_matches = (
        len(query_terms) if len(query_terms) <= 2 else max(2, (len(query_terms) + 1) // 2)
    )
    scored: list[tuple[TextChunk, float]] = []
    for chunk, counter, length in zip(chunks, term_counts, lengths, strict=True):
        score = 0.0
        matched = 0
        for term in query_terms:
            frequency = counter.get(term, 0)
            if not frequency:
                continue
            matched += 1
            idf = math.log(
                1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            denominator = frequency + K1 * (1 - B + B * length / average_length)
            score += idf * frequency * (K1 + 1) / denominator
        if matched >= required_matches and score > 0:
            scored.append((chunk, score))

    if not scored:
        return []
    best = max(score for _, score in scored)
    cutoff = max(min_score, best * relative_cutoff)
    ranked = [(chunk, score) for chunk, score in scored if score >= cutoff]
    ranked.sort(key=lambda pair: (-pair[1], pair[0].content))
    return ranked[:limit]
