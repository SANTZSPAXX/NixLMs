import json, math, re, unicodedata
from pathlib import Path

STOPWORDS = {"a","o","as","os","um","uma","de","da","do","das","dos","em","no","na","por","para","com","que","e","ou","é","ser","sou","eu","você","voce","me","minha","meu","seu","sua","como","qual","quando","onde","isso","essa","esse","ao","à","já","mais","muito"}

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()

def tokenize(text: str) -> list[str]:
    return [t for t in normalize(text).split() if len(t) > 1 and t not in STOPWORDS]

def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback

def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def cosine(a, b) -> float:
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na and nb else 0.0
