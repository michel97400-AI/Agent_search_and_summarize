

# ── Définition JSON de l'outil pour le LLM ────────────────────────────────────
TOOLS_LIST = [
    {
        "type": "function",
        "function": {
            "name": "search_and_summarize","description": (

                "Utilise cet outil pour toute recherche web"
                "récentes, des actualités, des prix, ou tout fait incertain. "
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La question ou la requête à rechercher sur le web"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
    
]


def search_web(query, num_results=5):
    """Recherche sur le web avec DuckDuckGo et retourne les résultats avec URLs."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            return f"❌ Module ddgs non installé. Installe-le avec: pip install ddgs"
        
        # Utiliser DuckDuckGo qui est plus permissif que Google
        ddgs = DDGS()
        
        # Effectuer la recherche en français (région France)
        results = list(ddgs.text(query, region='fr-fr', max_results=num_results))
        
        if not results:
            return f"❌ Aucun résultat trouvé pour '{query}'"
        
        # Formater les résultats
        output = f"🔍 Résultats de recherche pour '{query}':\n\n"
        for i, result in enumerate(results, 5):
            title = result.get('title', 'Sans titre')
            url = result.get('href', '#')
            body = result.get('body', 'Pas de description')
            
            output += f"{i}. **{title}**\n"
            output += f"   🔗 {url}\n"
            output += f"   📝 {body[:150]}...\n\n"
        
        return output
    
    except Exception as e:
        return f"❌ Erreur lors de la recherche web: {str(e)}"

def fetch_webpage(url):
    """Récupère et extrait le contenu textuel d'une page web avec Trafilatura."""
    try:
        import trafilatura
        
        # Valider l'URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Télécharger la page
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Extraire le contenu avec trafilatura
        content = trafilatura.extract(response.text, include_comments=False, favor_precision=True)
        
        if not content:
            return f"❌ Impossible d'extraire le contenu de {url}"
        
        # Limiter à 4000 caractères pour éviter de dépasser les limites de tokens
        if len(content) > 4000:
            content = content[:4000] + "\n\n[...contenu tronqué...]"
        
        # Récupérer le titre
        metadata = trafilatura.extract_metadata(response.text)
        title = metadata.title if metadata and metadata.title else "Sans titre"
        
        output = f"📄 Contenu de: {url}\n"
        output += f"📋 Titre: {title}\n"
        output += f"{'='*60}\n\n"
        output += content
        
        return output
    
    except requests.exceptions.ConnectionError:
        return f"❌ Erreur de connexion: impossible d'accéder à {url}"
    except requests.exceptions.Timeout:
        return f"❌ Timeout: la page met trop de temps à charger"
    except requests.exceptions.HTTPError as e:
        return f"❌ Erreur HTTP {e.response.status_code}: {url}"
    except Exception as e:
        return f"❌ Erreur lors de la récupération de la page: {e}"

def search_and_summarize(query):
    """Recherche sur le web et extrait le contenu en texte de la page la plus pertinente."""
    try:
        # D'abord, faire une recherche avec plusieurs résultats
        search_results = search_web(query, num_results=5)
        
        if "❌" in search_results or "⚠️" in search_results:
            return search_results
        
        # Extraire toutes les URLs et titres des résultats
        import re
        urls = re.findall(r'🔗 (https?://[^\s\)]+)', search_results)
        titles = re.findall(r'\*\*([^*]+)\*\*', search_results)
        
        if not urls:
            return search_results  # Retourner juste les résultats si pas d'URL
        
        # Trouver la page la plus pertinente (correspondance avec la query)
        query_words = query.lower().split()
        best_url = urls[0]
        best_score = 0
        
        for i, (url, title) in enumerate(zip(urls, titles)):
            title_lower = title.lower()
            # Score basé sur les mots de la query présents dans le titre
            score = sum(1 for word in query_words if word in title_lower)
            # Bonus si le titre commence par un mot de la query
            if any(title_lower.startswith(word) for word in query_words):
                score += 2
            # Bonus pour Wikipedia (généralement plus fiable)
            if "wikipedia" in url.lower():
                score += 1
            # Pénalité pour les pages qui semblent être des variantes (III, Jr, etc.)
            if any(x in title for x in [" III", " II", " Jr", " Sr", "frère", "fils", "neveu"]):
                if not any(x in query for x in ["III", "II", "Jr", "frère", "fils", "neveu"]):
                    score -= 2
            
            if score > best_score:
                best_score = score
                best_url = url
        
        # Récupérer le contenu de la page la plus pertinente
        content = fetch_webpage(best_url)
        
        return f"📄 Source: {best_url}\n\n{content}"
    
    except Exception as e:
        return f"❌ Erreur lors de la recherche et résumé: {e}"






