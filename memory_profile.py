"""
memory_profile.py
─────────────────
Gère le profil utilisateur persistant (user_profile.json).
Chargé à chaque session, toujours injecté dans le prompt système.
Mis à jour automatiquement par le LLM après chaque échange.

Structure :
{
  "identity":     { "prénom": "Michel" },
  "personality":  { "traits": ["curieux"], "style": "direct" },
  "preferences":  { "outils": ["PyTorch"], "sujets": ["IA générative"] },
  "context":      { "métier": "alternant dév IA", "début": "22 juin 2026" },
  "meta":         { "last_updated": "2026-06-02T21:00:00" }
}
"""

import json
import re
from datetime import datetime
from pathlib import Path

PROFILE_FILE = Path("user_profile.json")

_SECTIONS = ["identity", "personality", "preferences", "context"]

# ─────────────────────────────────────────────
# Lecture / écriture
# ─────────────────────────────────────────────

def load_profile() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {s: {} for s in _SECTIONS} | {"meta": {"last_updated": None}}


def save_profile(profile: dict) -> None:
    profile.setdefault("meta", {})["last_updated"] = datetime.now().isoformat()
    PROFILE_FILE.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ─────────────────────────────────────────────
# Formatage pour le prompt système
# ─────────────────────────────────────────────

def format_profile_for_prompt(profile: dict) -> str:
    lines = []

    mapping = {
        "identity":    "Identité",
        "personality": "Personnalité & style",
        "preferences": "Préférences & intérêts",
        "context":     "Contexte professionnel",
    }

    for key, label in mapping.items():
        section = profile.get(key, {})
        if not section:
            continue
        lines.append(f"[{label}]")
        for k, v in section.items():
            val = ", ".join(v) if isinstance(v, list) else v
            lines.append(f"  {k}: {val}")

    if not lines:
        return ""
    return "Profil de l'utilisateur :\n" + "\n".join(lines)


# ─────────────────────────────────────────────
# Mise à jour automatique via LLM
# ─────────────────────────────────────────────

def update_profile_from_conversation(
    profile: dict,
    conversation_text: str,
    ask_llm_fn
) -> dict:
    """
    Demande au LLM d'extraire uniquement les infos personnelles sur
    l'utilisateur (PAS les résultats de recherche web) et met à jour
    le profil par merge.
    """
    current = json.dumps(
        {k: profile.get(k, {}) for k in _SECTIONS},
        ensure_ascii=False
    )

    prompt = (
        "Tu analyses un échange pour mettre à jour le profil personnel "
        "de l'utilisateur.\n\n"
        "RÈGLES STRICTES :\n"
        "- Extrait UNIQUEMENT ce que l'utilisateur dit de lui-même "
        "(prénom, caractère, habitudes, sentiments, préférences, contexte pro).\n"
        "- IGNORE tout ce qui vient d'une recherche web ou d'une source externe.\n"
        "- IGNORE les sujets techniques discutés (code, modèles IA, etc.).\n"
        "- Ne duplique pas ce qui existe déjà dans le profil actuel.\n\n"
        f"Profil actuel :\n{current}\n\n"
        f"Échange :\n{conversation_text}\n\n"
        "Réponds UNIQUEMENT avec un objet JSON représentant les champs à "
        "mettre à jour (merge partiel). Utilise les sections : "
        "identity, personality, preferences, context.\n"
        "Les valeurs peuvent être des strings ou des listes de strings.\n"
        "Exemple : {\"identity\": {\"prénom\": \"Michel\"}, "
        "\"personality\": {\"traits\": [\"curieux\", \"direct\"]}}\n"
        "Si rien de nouveau : {}"
    )

    try:
        response = ask_llm_fn(
            [{"role": "user", "content": prompt}],
            use_tools=False
        )
        raw = response["choices"][0]["message"].get("content", "{}")
        raw = re.sub(
            r"\[THINK\].*?\[/THINK\]",
            "",
            raw,
            flags=re.DOTALL
        ).strip()
        raw = re.sub(r"<[^>]+>.*?</[^>]+>", "", raw, flags=re.DOTALL)
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()

        from json import JSONDecoder

        # Extrait le premier objet JSON { ... }
        decoder = JSONDecoder()

        start = raw.find("{")
        if start == -1:
            return profile

        updates, end = decoder.raw_decode(raw[start:])
        if not updates:
            return profile

        changed = False
        for section, fields in updates.items():
            if section not in _SECTIONS or not isinstance(fields, dict):
                continue
            profile.setdefault(section, {})
            for k, v in fields.items():
                existing = profile[section].get(k)
                # Merge des listes sans doublons
                if isinstance(v, list) and isinstance(existing, list):
                    merged = existing + [x for x in v if x not in existing]
                    if merged != existing:
                        profile[section][k] = merged
                        changed = True
                elif v != existing:
                    profile[section][k] = v
                    changed = True

        if changed:
            save_profile(profile)
            print("\n🧠 Profil mis à jour")

    except Exception as e:
        print(f"\n⚠️  Mise à jour profil échouée : {e}")

    return profile