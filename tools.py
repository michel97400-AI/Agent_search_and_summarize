import requests
from memory_notes import save_note, search_notes, list_notes

# ── Définition JSON de l'outil pour le LLM ────────────────────────────────────
TOOLS_LIST = [
    {
        "type": "function",
        "function": {
            "name": "search_and_summarize",
            "description": (
                "Utilise cet outil pour toute recherche web récente, "
                "actualités, prix, faits incertains ou informations nécessitant "
                "une vérification. Recherche sur le web puis extrait le contenu "
                "de la page la plus pertinente."
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
    },
    {
    "type": "function",
    "function": {
        "name": "save_note",
        "description": "Sauvegarde une note utilisateur dans un fichier local.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["title", "content"]
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
            return f"❌ Module ddgs non installé. Installe-le avec: pip install duckduckgo-search"
        
        # Utiliser DuckDuckGo qui est plus permissif que Google
        ddgs = DDGS()
        
        # Effectuer la recherche en français (région France)
        results = list(ddgs.text(query, region='fr-fr', max_results=num_results))
        
        print(f"DEBUG search_web: Trouvé {len(results)} résultats")
        
        if not results:
            return f"❌ Aucun résultat trouvé pour '{query}'"
        
        # Formater les résultats
        output = f"🔍 Résultats de recherche pour '{query}':\n\n"
        for i, result in enumerate(results, 1):
            title = result.get('title', 'Sans titre')
            url = result.get('href', '#')
            body = result.get('body', 'Pas de description')
            
            output += f"{i}. **{title}**\n"
            output += f"   🔗 {url}\n"
            output += f"   📝 {body[:150]}...\n\n"
        
        return output
    
    except Exception as e:
        print(f"DEBUG search_web error: {type(e).__name__}: {str(e)}")
        return f"❌ Erreur lors de la recherche web: {str(e)}"

def explore_website(domain_url, query_words):
    """Explore un site web pour trouver du contenu pertinent.
    Essaie le sitemap, puis les pages principales comme /team/, /about/, etc."""
    try:
        from urllib.parse import urljoin, urlparse
        from bs4 import BeautifulSoup
        
        print(f"DEBUG: Exploration du site {domain_url}...")
        
        # Extraire le domaine
        parsed = urlparse(domain_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Essai 1: Chercher le sitemap.xml
        urls_to_check = []
        try:
            sitemap_url = f"{domain}/sitemap.xml"
            response = requests.get(sitemap_url, timeout=10)
            if response.status_code == 200:
                print(f"DEBUG: Sitemap trouvé !")
                soup = BeautifulSoup(response.text, 'xml')
                for loc in soup.find_all('loc'):
                    urls_to_check.append(loc.text)
        except:
            pass
        
        # Essai 2: Pages communes
        common_pages = [
            '/team', '/equipe', '/about', '/a-propos', '/qui-sommes-nous',
            '/management', '/dirigeants', '/leadership', '/contact',
            '/societe', '/presentation', '/our-team', '/staff'
        ]
        
        for page in common_pages:
            urls_to_check.append(urljoin(domain, page))
        
        # Parcourir les URLs trouvées
        for url in urls_to_check[:15]:  # Limiter à 15 pages
            try:
                print(f"DEBUG: Exploration {url}...")
                content = fetch_webpage(url)
                
                if "❌" not in content:
                    # Vérifier la pertinence
                    content_lower = content.lower()
                    match_count = sum(1 for word in query_words if word in content_lower)
                    
                    if match_count >= max(1, len(query_words) // 2):
                        print(f"DEBUG: Page pertinente trouvée !")
                        return (content, url)
            except:
                continue
        
        return None
    
    except Exception as e:
        print(f"DEBUG explore_website: {e}")
        return None

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
    """Recherche sur le web et extrait le contenu en texte de la page la plus pertinente.
    Escalade progressive : essaie 10 résultats, puis explore les sites en profondeur."""
    try:
        # Escalade progressive des résultats (commencer par 10)
        for num_results in [10, 20]:
            print(f"DEBUG: Tentative avec {num_results} résultats...")
            search_results = search_web(query, num_results=num_results)
            
            if "❌" in search_results:
                if num_results < 20:
                    continue  # Essayer avec plus de résultats
                else:
                    return search_results
            
            # Extraire toutes les URLs des résultats
            import re
            urls = re.findall(r'🔗 (https?://[^\s\)]+)', search_results)
            print(f"DEBUG: Trouvé {len(urls)} URLs")
            
            if not urls:
                if num_results < 20:
                    continue  # Essayer avec plus de résultats
                return search_results  # Retourner juste les résultats si pas d'URL
            
            # Essayer chaque URL jusqu'à trouver du contenu pertinent
            query_words = [w for w in query.lower().split() if len(w) > 2]
            best_content = None
            best_url = None
            
            for idx, url in enumerate(urls):
                print(f"Extraction contenu de {url} ({idx+1}/{len(urls)})...")
                try:
                    content = fetch_webpage(url)
                    if "❌" not in content:  # Si le contenu a été extrait
                        print(f"Contenu extrait avec succès")
                        # Vérifier si le contenu contient les mots-clés de la query
                        content_lower = content.lower()
                        match_count = sum(1 for word in query_words if word in content_lower)
                        
                        print(f"DEBUG: {match_count}/{len(query_words)} mots-clés trouvés")
                        
                        # Si au moins la moitié des mots-clés sont trouvés, c'est bon
                        if match_count >= max(1, len(query_words) // 2):
                            best_content = content
                            best_url = url
                            print(f"Contenu pertinent trouvé !")
                            break
                        else:
                            # Pas pertinent sur cette page, explorer le site en profondeur
                            print(f"Page non pertinente, exploration du site...")
                            result = explore_website(url, query_words)
                            if result:
                                best_content, best_url = result
                                break
                except Exception as e:
                    print(f"DEBUG: Erreur extraction {url}: {e}")
                    continue
            
            # Si on a trouvé du contenu pertinent, le retourner
            if best_content and best_url:
                return f"📄 Source: {best_url}\n\n{best_content}"
            
            # Sinon, si on a au moins des URLs, essayer la première
            if urls:
                print(f"DEBUG: Pas de contenu pertinent, essai exploration du premier site...")
                result = explore_website(urls[0], query_words)
                if result:
                    content, url = result
                    return f"📄 Source: {url}\n\n{content}"
        
        # Si après avoir essayé 20 résultats on n'a rien trouvé
        return f"❌ Impossible de trouver des résultats pertinents pour '{query}' après avoir exploré les sites web."
    
    except Exception as e:
        print(f"DEBUG search_and_summarize: {type(e).__name__}: {str(e)}")
        return f"❌ Erreur lors de la recherche et résumé: {e}"

AVAILABLE_TOOLS = {
    "search_and_summarize": search_and_summarize,
    "save_note": save_note,
    "search_notes": search_notes,
    "list_notes": list_notes,
}




