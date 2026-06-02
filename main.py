"""
chat.py
───────
Assistant Arés avec mémoire à deux niveaux :
  - user_profile.json  : profil personnel, toujours en contexte
  - notes/             : notes à la demande, retrouvées via outils
"""

import json
import re
import requests
from pathlib import Path

from tools import TOOLS_LIST, AVAILABLE_TOOLS
from memory_profile import (
    load_profile,
    format_profile_for_prompt,
    update_profile_from_conversation,
)

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


# ─────────────────────────────────────────────
# Nettoyage reasoning
# ─────────────────────────────────────────────

def clean_reasoning_output(text: str) -> str:
    if not text:
        return ""
    for pattern in [
        r"\[THINK\].*?\[/THINK\]",
        r"<thinking>.*?</thinking>",
        r"\[REASONING\].*?\[/REASONING\]",
        r"<reasoning>.*?</reasoning>",
    ]:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


# ─────────────────────────────────────────────
# Appel LM Studio
# ─────────────────────────────────────────────

def ask_llm(messages: list, use_tools: bool = True) -> dict:
    payload = {
        "model": "local-model",
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 2000,
    }
    if use_tools:
        payload["tools"] = TOOLS_LIST
    response = requests.post(LM_STUDIO_URL, json=payload, timeout=300)
    response.raise_for_status()
    return response.json()


# ─────────────────────────────────────────────
# Exécution d'un outil
# ─────────────────────────────────────────────

def call_tool(name: str, arguments: dict) -> str:
    tool_fn = AVAILABLE_TOOLS.get(name)
    if tool_fn is None:
        return f"Outil inconnu : {name}"
    try:
        return tool_fn(**arguments)
    except Exception as e:
        return f"Erreur lors de l'exécution de {name}: {e}"


# ─────────────────────────────────────────────
# Traitement d'un tour (avec chaîne d'outils)
# ─────────────────────────────────────────────

def process_turn(messages: list) -> str:
    """
    Gère un tour complet avec support de chaîne d'outils
    (le LLM peut appeler plusieurs outils successivement).
    """
    MAX_TOOL_ROUNDS = 5

    for _ in range(MAX_TOOL_ROUNDS):
        response = ask_llm(messages, use_tools=True)
        assistant_message = response["choices"][0]["message"]
        tool_calls = assistant_message.get("tool_calls")

        if not tool_calls:
            return clean_reasoning_output(
                assistant_message.get("content", "")
            )

        messages.append(assistant_message)

        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])
            print(f"\n🔧 Appel outil : {name}({args})")

            result = call_tool(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": str(result)
            })

    # Réponse finale sans outils après la limite
    final = ask_llm(messages, use_tools=False)
    return clean_reasoning_output(
        final["choices"][0]["message"].get("content", "")
    )


# ─────────────────────────────────────────────
# Prompt système
# ─────────────────────────────────────────────

def build_system_prompt(profile: dict) -> str:
    base = (
        "Tu es Arés, un assistant serviable, précis et concis.\n"
        "Utilise les outils disponibles pour :\n"
        "  - Rechercher des informations récentes (web)\n"
        "  - Sauvegarder une note quand l'utilisateur le demande "
        "(save_note)\n"
        "  - Retrouver des notes passées si besoin (search_notes, "
        "list_notes)\n\n"
        "Concernant la mémoire :\n"
        "  - Les notes ne sont PAS dans ton contexte par défaut : "
        "utilise search_notes pour les retrouver.\n"
        "  - Ne sauvegarde des notes QUE si l'utilisateur le demande "
        "explicitement.\n"
    )
    profile_ctx = format_profile_for_prompt(profile)
    return f"{base}\n{profile_ctx}" if profile_ctx else base


# ─────────────────────────────────────────────
# Chat principal
# ─────────────────────────────────────────────

def chat():
    # Chargement du profil (léger, toujours en mémoire)
    profile = load_profile()
    has_profile = any(profile.get(s) for s in ["identity", "personality",
                                                "preferences", "context"])
    if has_profile:
        name = profile.get("identity", {}).get("prénom", "")
        print(f"🧠 Profil chargé{f' — Bonjour {name} !' if name else ''}\n")

    messages = [{"role": "system", "content": build_system_prompt(profile)}]
    session_log: list[tuple[str, str]] = []

    while True:
        user_input = input("Moi: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Au revoir !")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            reply = process_turn(messages)
            print(f"\nArés: {reply}\n")
            messages.append({"role": "assistant", "content": reply})
            session_log.append((user_input, reply))

            # Mise à jour du profil tous les 2 échanges
            if True:
                convo_text = "\n".join(
                    f"Utilisateur : {u}\nArés : {a}"
                    for u, a in session_log[-2:]
                )
                profile = update_profile_from_conversation(
                    profile, convo_text, ask_llm
                )
                # Rafraîchit le prompt système si le profil a changé
                messages[0]["content"] = build_system_prompt(profile)

        except requests.RequestException as e:
            print(f"\n❌ Erreur réseau : {e}\n")
        except Exception as e:
            print(f"\n❌ Erreur : {e}\n")


if __name__ == "__main__":
    chat()