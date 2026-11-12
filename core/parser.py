"""Stage Hunter Agent - Module de parsing et normalisation HTML / Markdown.

Permet de convertir des fiches HTML brutes en Markdown condensé économe en tokens
et de relire les exports Markdown générés par l'extension de navigateur.
"""

import re
from typing import Dict, List
from bs4 import BeautifulSoup


def html_to_condensed_markdown(html_content: str, max_paragraphs: int = 15) -> Dict[str, str]:
    """Nettoie le code HTML d'une fiche de poste et extrait un Markdown condensé."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Suppression des balises polluantes ou non sémantiques
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "svg", "iframe", "button", "aside"]):
        tag.decompose()

    # Détection du titre principal
    title = ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    elif soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)
    else:
        title = "Poste sans titre"

    # Extraction des blocs textuels et listes à puces
    body = soup.body or soup
    raw_text = body.get_text(separator="\n")

    lines = [line.strip() for line in raw_text.splitlines()]
    # Conservation de toutes les lignes significatives sans seuil arbitraire de longueur
    clean_lines = [l for l in lines if len(l) >= 4 and not re.match(r"^(\s*|[-*_•·#]{1,3})$", l)]

    condensed_text = "\n".join(clean_lines[:60])

    return {
        "title": title,
        "content_markdown": condensed_text
    }


def parse_extension_markdown(markdown_text: str) -> List[Dict]:
    """Analyse le contenu d'un fichier Markdown exporté par l'extension Chrome.

    Retourne la liste des offres structurées.
    """
    offers: List[Dict] = []
    # Découpage par bloc d'offre (## OFFRE_X:)
    sections = re.split(r"\n##\s+OFFRE_\d+:\s*", markdown_text)

    for section in sections[1:]:  # On ignore l'en-tête général
        lines = section.strip().splitlines()
        if not lines:
            continue

        title = lines[0].strip()
        url = ""
        stack = ""
        is_certified = False
        content_lines: List[str] = []

        is_extracting_content = False
        for line in lines[1:]:
            line_str = line.strip()
            if line_str.startswith("- **URL :**"):
                url = line_str.replace("- **URL :**", "").strip()
            elif line_str.startswith("- **Technologies identifiées :**"):
                stack = line_str.replace("- **Technologies identifiées :**", "").strip()
            elif line_str.startswith("- **Mention explicite Bac+2/3 :**"):
                val = line_str.replace("- **Mention explicite Bac+2/3 :**", "").strip()
                is_certified = "OUI" in val.upper()
            elif line_str.startswith("### Extrait textuel :"):
                is_extracting_content = True
            elif line_str.startswith("---"):
                break
            elif is_extracting_content:
                content_lines.append(line)

        content = "\n".join(content_lines).strip()

        offers.append({
            "title": title,
            "url": url,
            "stack": stack,
            "is_certified_bac23": is_certified,
            "content": content
        })

    return offers
