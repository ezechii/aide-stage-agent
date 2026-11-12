"""Stage Hunter Agent - Module d'évaluation LLM structuré (Tamis 2).

Utilise le SDK Google GenAI (Gemini Flash) avec validation stricte via Pydantic
pour qualifier les offres ayant franchi le Tamis 1 Regex.
"""

import os
import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Chargement automatique des variables d'environnement
load_dotenv()


class OfferEvaluation(BaseModel):
    """Schéma Pydantic strict pour la qualification d'une offre."""
    is_compatible_bac2_3: bool = Field(
        description="Vrai si l'offre est accessible à un profil Bac+2 ou Bac+3 (Stage d'application, 3 à 4 mois). Faux s'il s'agit d'un PFE ou Bac+5 masqué."
    )
    duration_months: Optional[int] = Field(
        default=None,
        description="Durée estimée du stage en mois (ex: 3, 4, 6) si mentionnée ou déductible."
    )
    score_matching: int = Field(
        ge=0,
        le=100,
        description="Score de pertinence de 0 à 100 pour le profil d'Ezéchiel DJEBE (Python, C++, Linux, Signal, Électronique/Embarqué)."
    )
    target_stack: List[str] = Field(
        default_factory=list,
        description="Technologies ou compétences requises/souhaitées identifiées dans le texte."
    )
    verdict_summary: str = Field(
        description="Synthèse concise en une phrase expliquant l'adéquation ou les réserves."
    )
    action_recommended: str = Field(
        description="Décision finale recommandée : 'POSTULER', 'A_VERIFIER', ou 'REJETER'."
    )


PROMPT_SYSTEM = """Tu es l'évaluateur technique expert du pipeline Stage-Hunter pour Ezéchiel DJEBE.
Profil du candidat :
- Étudiant en 2ème année de cycle préparatoire intégré (Bac+2) à l'ISEP Paris.
- Recherche : Stage technique d'application de 3 à 4 mois (début possible mi-avril 2027).
- Compétences réelles : Python, C++, Linux, Git, SQL, notions d'électronique, traitement du signal, Bash.
- RÈGLE ABSOLUE : Rejeter formellement toute offre de fin d'études (PFE, 6 mois, réservée aux étudiants en dernière année d'école d'ingénieur ou Master 2 Bac+5).
- Si l'offre est compatible Bac+2/3 ou ouverte aux stages de 2ème année / BUT / Licence, valide-la.
- Calcule un score_matching de 0 à 100 reflétant l'alignement avec les technologies Python / C++ / Linux / Embarqué / Traitement du signal.
- Réponds STRICTEMENT au format JSON correspondant au schéma demandé."""


def evaluate_offer_with_llm(offer_title: str, offer_content: str, api_key: Optional[str] = None) -> OfferEvaluation:
    """Évalue une offre condensée via Gemini Flash et retourne une structure validée par Pydantic."""
    effective_key = api_key or os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    prompt_user = f"""Analyse cette offre de stage et fournis ton verdict structuré :

TITRE DE L'OFFRE :
{offer_title}

EXTRAIT CONDENSÉ DU POSTE :
{offer_content}
"""

    if not effective_key or effective_key.strip() in ("", "your_gemini_api_key_here"):
        # Mode dégradé sécurisé si aucune clé n'est encore configurée
        return OfferEvaluation(
            is_compatible_bac2_3=True,
            duration_months=3,
            score_matching=75,
            target_stack=["Python", "Linux"],
            verdict_summary="Évaluation simulée (GEMINI_API_KEY non configurée dans .env).",
            action_recommended="A_VERIFIER"
        )

    # 1. Tentative via le SDK officiel moderne google-genai
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=effective_key)
        response = client.models.generate_content(
            model=model_name,
            contents=f"{PROMPT_SYSTEM}\n\n{prompt_user}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=OfferEvaluation,
                temperature=0.1,
            ),
        )
        data = json.loads(response.text)
        return OfferEvaluation.model_validate(data)
    except ImportError:
        pass
    except Exception as e:
        # Si erreur d'API (ex: modèle non trouvé ou quota), repli sur google.generativeai
        pass

    # 2. Tentative via l'ancien SDK google-generativeai
    try:
        import google.generativeai as legacy_genai

        legacy_genai.configure(api_key=effective_key)
        model = legacy_genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content(f"{PROMPT_SYSTEM}\n\n{prompt_user}")
        data = json.loads(response.text)
        return OfferEvaluation.model_validate(data)
    except Exception as err:
        return OfferEvaluation(
            is_compatible_bac2_3=False,
            duration_months=None,
            score_matching=0,
            target_stack=[],
            verdict_summary=f"Erreur d'appel API : {str(err)[:120]}",
            action_recommended="A_VERIFIER"
        )
