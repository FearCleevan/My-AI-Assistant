import re

_PREFIX = re.compile(
    r"^(please\s+)?"
    r"(learn|teach me|tell me|explain|study|show me|i want to learn|"
    r"give me info on|find out about|research|crawl|get info on|"
    r"fetch|download info about)\s+"
    r"(everything|anything|all)?\s*"
    r"(you can)?\s*"
    r"(about|on|regarding|for)?\s*",
    re.IGNORECASE,
)

_SUFFIX = re.compile(
    r"\s+(and\s+(its|their|the)\s+\w+|"
    r"framework|documentation|docs|tutorial|guide|"
    r"overview|basics|intro|introduction|concepts|"
    r"examples?|tips?|tricks?|references?|api)s?$",
    re.IGNORECASE,
)


def extract_topic(text: str) -> str:
    """
    Extract a clean topic name from natural language.

    Examples:
      "Learn everything about React JS and its framework"  → "React JS"
      "study python documentation"                         → "Python"
      "Tell me about Next.js"                              → "Next.Js"
    """
    t = text.strip()
    t = _PREFIX.sub("", t)
    t = _SUFFIX.sub("", t)
    t = t.strip()
    return t.title() if t else text.strip()
