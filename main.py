import json
import re
import requests

from tools import TOOLS_LIST, AVAILABLE_TOOLS

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


# ─────────────────────────────────────────────
# Nettoyage des sorties reasoning
# ─────────────────────────────────────────────
def clean_reasoning_output(text: str) -> str:

    if not text:
        return ""

    patterns = [
        r"\[THINK\].*?\[/THINK\]",
        r"<thinking>.*?</thinking>",
        r"\[REASONING\].*?\[/REASONING\]",
        r"<reasoning>.*?</reasoning>",
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


# ─────────────────────────────────────────────
# Exécution d'un outil
# ─────────────────────────────────────────────
def call_tool(name: str, arguments: dict):

    tool_function = AVAILABLE_TOOLS.get(name)

    if tool_function is None:
        return f"Outil inconnu : {name}"

    try:
        return tool_function(**arguments)

    except Exception as e:
        return f"Erreur lors de l'exécution de {name}: {e}"


# ─────────────────────────────────────────────
# Appel LM Studio
# ─────────────────────────────────────────────
def ask_llm(messages, use_tools=True):

    payload = {
        "model": "local-model",
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 2000,
    }

    if use_tools:
        payload["tools"] = TOOLS_LIST

    response = requests.post(
        LM_STUDIO_URL,
        json=payload,
        timeout=300
    )

    response.raise_for_status()

    return response.json()


# ─────────────────────────────────────────────
# Chat principal
# ─────────────────────────────────────────────
def chat():

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es Arés, un assistant serviable, précis et concis. "
                "Utilise les outils lorsque nécessaire pour obtenir des "
                "informations récentes ou vérifier des faits."
            )
        }
    ]

    while True:

        user_input = input("Moi: ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("Au revoir !")
            break

        messages.append({
            "role": "user",
            "content": user_input
        })

        try:

            # Premier appel : le modèle peut utiliser des outils
            response = ask_llm(messages, use_tools=True)

            assistant_message = response["choices"][0]["message"]

            tool_calls = assistant_message.get("tool_calls")

            # ─────────────────────────────
            # Cas : appel d'outil
            # ─────────────────────────────
            if tool_calls:

                messages.append(assistant_message)

                for tool_call in tool_calls:

                    function_name = tool_call["function"]["name"]

                    arguments = json.loads(
                        tool_call["function"]["arguments"]
                    )

                    print(
                        f"\n🔧 Appel outil : "
                        f"{function_name}({arguments})"
                    )

                    tool_result = call_tool(
                        function_name,
                        arguments
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": str(tool_result)
                    })

                # Deuxième appel : réponse finale
                final_response = ask_llm(
                    messages,
                    use_tools=False
                )

                final_text = (
                    final_response["choices"][0]["message"]["content"]
                )

                final_text = clean_reasoning_output(final_text)

                print(f"\nBot: {final_text}\n")

                messages.append({
                    "role": "assistant",
                    "content": final_text
                })

            # ─────────────────────────────
            # Cas : réponse normale
            # ─────────────────────────────
            else:

                content = assistant_message.get(
                    "content",
                    ""
                )

                content = clean_reasoning_output(content)

                print(f"\nBot: {content}\n")

                messages.append({
                    "role": "assistant",
                    "content": content
                })

        except Exception as e:
            print(f"\n❌ Erreur : {e}\n")


if __name__ == "__main__":
    chat()