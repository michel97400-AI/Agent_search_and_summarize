import requests
import re
from tools import search_and_summarize

def clean_reasoning_output(text):
    """
    Nettoie les outputs de modèles avec reasoning (Mistral 8B Reasoning, etc.)
    Supprime les sections de pensée et ne garde que la réponse finale.
    """
    # Supprimer les balises [THINK]...[/THINK]
    text = re.sub(r'\[THINK\].*?\[/THINK\]', '', text, flags=re.DOTALL)
    
    # Supprimer les balises <thinking>...</thinking>
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    
    # Supprimer les balises [REASONING]...[/REASONING]
    text = re.sub(r'\[REASONING\].*?\[/REASONING\]', '', text, flags=re.DOTALL)
    
    # Supprimer les balises <reasoning>...</reasoning>
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
    
    # Nettoie les espaces blancs excessifs
    text = re.sub(r'\n\s*\n', '\n', text)  # Supprime les lignes vides multiples
    text = text.strip()
    
    return text

def call_tools(tool_name, arguments):
    if tool_name == "search_and_summarize":
        query = arguments.get("query") or "."
        return search_and_summarize(query)


def chat():
    while True:

        user_input = input("Moi: ")
        if user_input.lower() == "exit":
            print("Au revoir!")
            break

        messages = [{"role": "user", "content": user_input}]

        system_prompt = {
            "role": "system",
            "content": "Tu es Arés un assistant serviable et concis."
        }

        payload = {
            "model": "local-model",
            "messages": [system_prompt] + messages,
            "temperature": 0.6,
            "max_tokens": 2000,
            "stream": False
        }

        try:
            response = requests.post(
                f"http://localhost:1234/v1/chat/completions",
                json=payload,
            )
        except response.status_code != 200:
            return f"Erreur LM Studio: {response.text}", response.status_code
        
        data = response.json()
        ai_response = data["choices"][0]["message"]["content"]
        ai_response = clean_reasoning_output(ai_response)
        print("Bot:", ai_response)


if __name__ == "__main__":
    chat()