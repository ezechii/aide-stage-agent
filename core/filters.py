"""Stage Hunter Agent - Module de filtrage Regex (Tamis 1).

Ce module applique un premier tamis local (0 token) pour :
- Éliminer strictement les offres Bac+5, Bac+4/5, PFE, stages de fin d'études, 6 mois stricts, Master.
- Retenir et qualifier positivement les offres Bac+2 / Bac+3 (ex: "BAC+2/+3", "4 à 6 mois",
  "2ème année d'école d'ingénieur", "3ème année d'école d'ingénieur").
"""

import re
from typing import Dict, List, Optional, Tuple

# Motifs d'exclusion stricte (Tamis négatif Bac+5, fin d'études, PFE, Césure, 6 mois stricts)
REJECT_PATTERNS = [
    re.compile(r"\bbac\s*\+?\s*(?:4\s*[/ou,-]\s*5|4|5)\b", re.IGNORECASE),
    re.compile(r"\bmaster(?:\s*[12])?\b", re.IGNORECASE),
    re.compile(r"\bm[12]\b", re.IGNORECASE),
    re.compile(r"\bpfe\b", re.IGNORECASE),
    re.compile(r"\bfin\s*d['’]études\b", re.IGNORECASE),
    re.compile(r"\bdernière\s*année\b", re.IGNORECASE),
    re.compile(r"\b5[èe]me\s*année\b", re.IGNORECASE),
    re.compile(r"\bdernière\s*année\s*d['’ ]?école", re.IGNORECASE),
    re.compile(r"\bcésure\b", re.IGNORECASE),
    re.compile(r"\bstage\s*de\s*fin\s*d['’]études\b", re.IGNORECASE),
    re.compile(r"\bprojet\s*de\s*fin\s*d['’]études\b", re.IGNORECASE),
]

# Motifs de validation explicite de niveau Bac+2 / Bac+3 (Tamis positif)
POSITIVE_PATTERNS = [
    re.compile(r"\bbac\s*\+\s*2(?:\s*[\/+\-]\s*\+?\s*3)?\b", re.IGNORECASE),
    re.compile(r"\bbac\s*\+\s*3\b", re.IGNORECASE),
    re.compile(r"\b2[èe]me\s*(?:ou\s*3[èe]me\s*)?année\s*d['’ ]?école\s*d['’ ]?ingénieur", re.IGNORECASE),
    re.compile(r"\b3[èe]me\s*année\s*d['’ ]?école\s*d['’ ]?ingénieur", re.IGNORECASE),
    re.compile(r"\b2[èe]me\s*année\b", re.IGNORECASE),
    re.compile(r"\b3[èe]me\s*année\b", re.IGNORECASE),
    re.compile(r"\bl2\b|\bl3\b", re.IGNORECASE),
    re.compile(r"\bbut\s*2\b|\bbut\s*3\b", re.IGNORECASE),
    re.compile(r"\bcycle\s*préparatoire\b", re.IGNORECASE),
    re.compile(r"\bstage\s*d['’]application\b", re.IGNORECASE),
    re.compile(r"\bstage\s*technique\b", re.IGNORECASE),
    re.compile(r"\b[34]\s*(?:à|et|-|\/)\s*6\s*mois\b", re.IGNORECASE),
    re.compile(r"\b3\s*(à|et|-)\s*4\s*mois\b", re.IGNORECASE),
    re.compile(r"\b4\s*mois\b", re.IGNORECASE),
    re.compile(r"\btechnicien\b", re.IGNORECASE),
]

# Dictionnaire des compétences et technologies cibles
TECH_KEYWORDS = {
    "Python": re.compile(r"\bpython\b", re.IGNORECASE),
    "C++": re.compile(r"\bc\+\+\b", re.IGNORECASE),
    "C": re.compile(r"\b(?<!\w)c(?!\w|\+|\#)", re.IGNORECASE),
    "Linux": re.compile(r"\blinux\b|\bunix\b|\bdebian\b|\bubuntu\b", re.IGNORECASE),
    "Bash": re.compile(r"\bbash\b|\bshell\b", re.IGNORECASE),
    "Git": re.compile(r"\bgit\b|\bgithub\b|\bgitlab\b", re.IGNORECASE),
    "SQL": re.compile(r"\bsql\b|\bpostgresql\b|\bmysql\b|\bsqlite\b", re.IGNORECASE),
    "Docker": re.compile(r"\bdocker\b|\bconteneur\b", re.IGNORECASE),
    "Signal": re.compile(r"\btraitement\s*du\s*signal\b|\bsignal\s*processing\b|\bfiltrage\b|\bfft\b", re.IGNORECASE),
    "VHDL": re.compile(r"\bvhdl\b|\bfpga\b", re.IGNORECASE),
    "Électronique / Embarqué": re.compile(r"\b(embarqu[ée]|microcontr[ôo]leur|stm32|arduino|raspberry)\b", re.IGNORECASE),
    "Réseaux": re.compile(r"\b(tcp/ip|sockets?|wireshark|protocoles?\s*r[ée]seau)\b", re.IGNORECASE),
}


def evaluate_rejection(text: str) -> Tuple[bool, Optional[str]]:
    """Vérifie si le texte contient un motif d'exclusion rédhibitoire (Bac+4/5, Master, PFE, 6 mois stricts)."""
    # 1. Vérification des motifs d'exclusion stricts
    for pattern in REJECT_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group(0)

    # 2. Gestion de la durée : on exclut le "6 mois" strict, mais PAS les plages "3 à 6 mois" ou "4 à 6 mois"
    text_sans_plages = re.sub(r"\b[34]\s*(?:à|et|-|\/)\s*6\s*mois\b", "", text, flags=re.IGNORECASE)
    m_6m = re.search(r"\b6\s*mois\b", text_sans_plages, re.IGNORECASE)
    if m_6m:
        return True, "6 mois (strict)"

    return False, None


def evaluate_positive_signals(text: str) -> List[str]:
    """Extrait les mentions explicites compatibles Bac+2/Bac+3."""
    signals = []
    for pattern in POSITIVE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            if isinstance(matches[0], tuple):
                signals.append(matches[0][0])
            else:
                signals.append(matches[0])
    return list(set(signals))


def extract_technologies(text: str) -> List[str]:
    """Identifie la stack technique présente dans le texte."""
    detected = []
    for tech_name, pattern in TECH_KEYWORDS.items():
        if pattern.search(text):
            detected.append(tech_name)
    return detected


def filter_offer_text(title: str, text: str) -> Dict:
    """Effectue une analyse complète Tamis 1 sur le titre et le corps de l'offre."""
    full_text = f"{title}\n{text}"
    is_rejected, reason = evaluate_rejection(full_text)
    positive_signals = evaluate_positive_signals(full_text)
    stack = extract_technologies(full_text)

    status = "REJETEE" if is_rejected else ("VALIDEE_BAC23" if positive_signals else "A_VERIFIER_LLM")

    return {
        "title": title,
        "is_rejected": is_rejected,
        "rejection_reason": reason,
        "positive_signals": positive_signals,
        "stack": stack,
        "status": status,
    }
