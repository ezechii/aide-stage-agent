"""Stage Hunter Agent - Module de crawling autonome des portails carrières.

Permet à l'agent d'aspirer de manière 100% autonome les offres d'un portail
(ex: Thales, Safran, etc.), de générer l'export Markdown pré-filtré (Tamis 1),
et de déclencher automatiquement la chaîne d'évaluation batch.
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# Configuration encodage console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.filters import evaluate_rejection, evaluate_positive_signals, extract_technologies
from core.parser import html_to_condensed_markdown


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def crawl_thales(query: str = "stage", max_pages: int = 3) -> list:
    """Aspire et pré-filtre les offres du portail carrières Thales."""
    print(f"🌐 Lancement du scan Thales (requête: '{query}', {max_pages} page(s))...")
    session = requests.Session()
    session.headers.update(HEADERS)

    job_entries = []
    seen_ids = set()

    for page_idx in range(max_pages):
        from_offset = page_idx * 10
        search_url = f"https://careers.thalesgroup.com/fr/fr/search-results?keywords={query}&from={from_offset}"
        print(f"  📄 Scan page {page_idx + 1} ({search_url})...")

        try:
            resp = session.get(search_url, timeout=15)
            if resp.status_code != 200:
                print(f"  ⚠️ Erreur HTTP {resp.status_code}")
                continue

            m = re.search(r"phApp\.ddo\s*=\s*(\{.*?\});\s*(?:window|phApp|var|<)", resp.text, re.DOTALL)
            if not m:
                print("  ⚠️ Structure phApp.ddo non détectée sur cette page.")
                continue

            data = json.loads(m.group(1))
            refine_data = data.get("eagerLoadRefineSearch", {}).get("data", {})
            jobs = refine_data.get("jobs", [])

            for j in jobs:
                jid = j.get("jobId")
                if not jid or jid in seen_ids:
                    continue
                seen_ids.add(jid)

                # Priorité aux offres en France ou télétravail/proximité
                country = j.get("country", "")
                if country and "France" not in country:
                    continue

                job_entries.append({
                    "id": jid,
                    "title": j.get("title", "Sans titre"),
                    "city": j.get("city", "France"),
                    "applyUrl": j.get("applyUrl", ""),
                    "detailUrl": f"https://careers.thalesgroup.com/fr/fr/job/{jid}",
                })
        except Exception as err:
            print(f"  ❌ Erreur lors du scraping de la page {page_idx + 1} : {err}")

    print(f"✅ {len(job_entries)} offre(s) candidate(s) trouvée(s) en France. Récupération des descriptions...")

    qualified_offers = []
    rejected_count = 0

    for idx, entry in enumerate(job_entries, 1):
        jid = entry["id"]
        title = entry["title"]
        url = entry["detailUrl"]
        print(f"  [{idx}/{len(job_entries)}] Extraction fiche : {title[:55]}...")

        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                continue

            # Extraction de la description via phApp.ddo ou DOM
            description = ""
            m_job = re.search(r"phApp\.ddo\s*=\s*(\{.*?\});\s*(?:window|phApp|var|<)", resp.text, re.DOTALL)
            if m_job:
                try:
                    job_data = json.loads(m_job.group(1))
                    description = job_data.get("jobDetail", {}).get("data", {}).get("job", {}).get("description", "")
                except Exception:
                    pass

            if not description:
                soup = BeautifulSoup(resp.text, "html.parser")
                desc_div = soup.find("div", class_=re.compile(r"jd-info|job-description", re.I))
                description = desc_div.decode_contents() if desc_div else (soup.body.get_text() if soup.body else "")

            # Nettoyage et conversion en texte
            clean_text = BeautifulSoup(description, "html.parser").get_text(separator="\n")

            # TAMIS 1 : Rejet strict des Bac+4/5 / Master / 6 mois / PFE / Césure
            is_rej, rej_pattern = evaluate_rejection(f"{title}\n{clean_text}")
            if is_rej:
                print(f"    ❌ Rejet immédiat Tamis 1 ({rej_pattern})")
                rejected_count += 1
                continue

            positive_signals = evaluate_positive_signals(f"{title}\n{clean_text}")
            stack = extract_technologies(f"{title}\n{clean_text}")

            # Conservation des lignes textuelles informatives sans coupure arbitraire
            clean_paras = [p.strip() for p in clean_text.splitlines() if len(p.strip()) >= 4 and not re.match(r"^(\s*|[-*_•·#]{1,3})$", p.strip())]
            condensed = "\n".join(clean_paras[:50])

            qualified_offers.append({
                "title": title,
                "url": url,
                "city": entry["city"],
                "stack": ", ".join(stack) or "Non spécifiée",
                "isCertifiedBac23": bool(positive_signals),
                "content": condensed,
            })
            print(f"    ✨ Retenue par Tamis 1 (Stack: {', '.join(stack) or 'Général'})")

        except Exception as err:
            print(f"    ⚠️ Erreur lecture fiche {jid} : {err}")

    print(f"\n🎯 Synthèse Tamis 1 Thales :")
    print(f"• Total analysé : {len(job_entries)}")
    print(f"• Retenues (Tamis 1) : {len(qualified_offers)}")
    print(f"• Éliminées (Bac+5 / 6 mois / PFE) : {rejected_count}")

    return qualified_offers


def save_to_markdown(offers: list, prefix: str = "thales_live") -> Path:
    """Exporte les offres pré-filtrées dans output/raw_markdown/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "output" / "raw_markdown"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{prefix}_{timestamp}.md"

    md = f"# SOURCING STAGES & ALTERNANCES — BRUT PRÉ-FILTRÉ (TAMIS 1)\n\n"
    md += f"*Date : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*\n"
    md += f"*Nombre d'offres qualifiées (Tamis 1) : {len(offers)}*\n\n---\n\n"

    for i, o in enumerate(offers, 1):
        md += f"## OFFRE_{i}: {o['title']} ({o.get('city', 'France')})\n"
        md += f"- **URL :** {o['url']}\n"
        md += f"- **Technologies identifiées :** {o['stack']}\n"
        md += f"- **Mention explicite Bac+2/3 :** {'OUI' if o['isCertifiedBac23'] else 'À vérifier par LLM'}\n\n"
        md += f"### Extrait textuel :\n{o['content']}\n\n---\n\n"

    out_file.write_text(md, encoding="utf-8")
    print(f"💾 Fichier Markdown généré : {out_file}")
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Crawler autonome pour Stage Hunter")
    parser.add_argument("--source", default="thales", choices=["thales"], help="Source portail à scanner")
    parser.add_argument("--query", default="stage logiciel", help="Mot-clé de recherche")
    parser.add_argument("--pages", type=int, default=3, help="Nombre de pages de résultats à parcourir")
    parser.add_argument("--auto-batch", action="store_true", default=True, help="Lancer automatiquement run_batch.py")
    args = parser.parse_args()

    offers = []
    if args.source == "thales":
        offers = crawl_thales(query=args.query, max_pages=args.pages)

    if not offers:
        print("⚠️ Aucune offre compatible trouvée sur ce filtre.")
        return

    md_path = save_to_markdown(offers, prefix=f"{args.source}_{args.query.replace(' ', '_')}")

    if args.auto_batch:
        print("\n🚀 Déclenchement automatique du pipeline de batch (Tamis 2 LLM)...")
        from cli.run_batch import main as run_batch_main
        # Appel direct avec le fichier généré
        sys.argv = [sys.argv[0], "--file", str(md_path)]
        run_batch_main()


if __name__ == "__main__":
    main()
