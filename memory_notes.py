"""
memory_notes.py
───────────────
Gère les notes persistantes dans un dossier notes/.
Jamais chargé automatiquement — uniquement via outils explicites.

Outils disponibles (à enregistrer dans tools.py) :
  - save_note(title, content, tags)  → sauvegarde une note
  - search_notes(query)              → recherche par mots-clés
  - list_notes()                     → liste toutes les notes
"""

import json
import re
from datetime import datetime
from pathlib import Path

NOTES_DIR = Path("notes")


# ─────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────

def _ensure_dir() -> None:
    NOTES_DIR.mkdir(exist_ok=True)


def _slug(title: str) -> str:
    """Convertit un titre en nom de fichier safe."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:60]


def _load_index() -> dict:
    """Charge l'index des notes (titre, tags, date, filename)."""
    index_file = NOTES_DIR / "index.json"
    if index_file.exists():
        try:
            return json.loads(index_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"notes": []}


def _save_index(index: dict) -> None:
    index_file = NOTES_DIR / "index.json"
    index_file.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ─────────────────────────────────────────────
# Outils publics
# ─────────────────────────────────────────────

def save_note(content: str, title: str = None, tags=None):
    """
    Sauvegarde une note dans notes/<slug>.md avec métadonnées.
    Met à jour l'index.
    Retourne un message de confirmation.
    """
    _ensure_dir()
    tags = tags or []
    date = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().isoformat()
    slug = _slug(title)

    # Évite les collisions de noms de fichiers
    filename = f"{date}_{slug}.md"
    filepath = NOTES_DIR / filename
    counter = 1
    while filepath.exists():
        filename = f"{date}_{slug}_{counter}.md"
        filepath = NOTES_DIR / filename
        counter += 1

    # Écrit le fichier Markdown avec frontmatter
    note_content = (
        f"---\n"
        f"title: {title}\n"
        f"date: {date}\n"
        f"tags: {', '.join(tags)}\n"
        f"---\n\n"
        f"{content.strip()}\n"
    )
    filepath.write_text(note_content, encoding="utf-8")

    # Met à jour l'index
    index = _load_index()
    # Supprime l'ancienne entrée si même titre
    index["notes"] = [n for n in index["notes"] if n["title"] != title]
    index["notes"].append({
        "title": title,
        "filename": filename,
        "date": date,
        "tags": tags,
        "updated": timestamp,
    })
    _save_index(index)

    return f"✅ Note sauvegardée : {filename}"


def search_notes(query: str, max_results: int = 3) -> str:
    """
    Recherche dans les notes par mots-clés (titre, tags, contenu).
    Retourne les extraits pertinents, pas les fichiers entiers.
    """
    _ensure_dir()
    index = _load_index()
    if not index["notes"]:
        return "Aucune note enregistrée."

    keywords = [w.lower() for w in query.split() if len(w) > 2]
    if not keywords:
        return "Requête trop courte."

    results = []

    for entry in index["notes"]:
        filepath = NOTES_DIR / entry["filename"]
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        content_lower = content.lower()

        # Score = nombre de mots-clés trouvés dans titre + tags + contenu
        score = sum(
            3 if kw in entry["title"].lower() else
            2 if any(kw in t.lower() for t in entry["tags"]) else
            1 if kw in content_lower else 0
            for kw in keywords
        )

        if score > 0:
            # Extrait un aperçu autour du premier mot-clé trouvé
            preview = _extract_preview(content, keywords)
            results.append((score, entry["title"], entry["date"], preview))

    if not results:
        return f"Aucune note trouvée pour : {query}"

    results.sort(reverse=True)
    output = [f"🔍 {len(results)} note(s) trouvée(s) pour « {query} » :"]
    for _, title, date, preview in results[:max_results]:
        output.append(f"\n📄 [{date}] {title}\n{preview}")

    return "\n".join(output)


def list_notes() -> str:
    """Retourne la liste de toutes les notes enregistrées."""
    _ensure_dir()
    index = _load_index()
    if not index["notes"]:
        return "Aucune note enregistrée."

    lines = [f"📚 {len(index['notes'])} note(s) :"]
    for n in sorted(index["notes"], key=lambda x: x["date"], reverse=True):
        tags = f"  [{', '.join(n['tags'])}]" if n["tags"] else ""
        lines.append(f"  • [{n['date']}] {n['title']}{tags}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Helper preview
# ─────────────────────────────────────────────

def _extract_preview(content: str, keywords: list[str], window: int = 200) -> str:
    """Extrait un aperçu centré sur le premier mot-clé trouvé."""
    # Supprime le frontmatter
    content = re.sub(r"^---.*?---\n", "", content, flags=re.DOTALL).strip()
    lower = content.lower()

    for kw in keywords:
        idx = lower.find(kw)
        if idx != -1:
            start = max(0, idx - window // 2)
            end = min(len(content), idx + window // 2)
            excerpt = content[start:end].strip()
            if start > 0:
                excerpt = "…" + excerpt
            if end < len(content):
                excerpt = excerpt + "…"
            return excerpt

    # Fallback : début du contenu
    return content[:window].strip() + ("…" if len(content) > window else "")