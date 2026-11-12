"""Stage Hunter Agent - Script CLI de traitement par lot (Batch Pipeline).

Prend en entrée un fichier Markdown pré-filtré issu de l'extension Chrome,
applique le Tamis 1 Regex de sécurité, évalue les offres via le Tamis 2 LLM,
et génère un tableau de bord HTML complet dans output/dashboards/.
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Configuration de l'encodage console sous Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ajout du dossier racine au sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.parser import parse_extension_markdown
from core.filters import filter_offer_text
from core.llm_evaluator import evaluate_offer_with_llm


def generate_html_dashboard(results: list, output_path: Path) -> None:
    """Génère un tableau de bord HTML moderne pour visualiser les offres qualifiées."""
    total = len(results)
    retained = sum(1 for r in results if r["evaluation"]["is_compatible_bac2_3"])
    rejected = total - retained

    cards_html = []
    for r in results:
        eval_data = r["evaluation"]
        is_ok = eval_data["is_compatible_bac2_3"]
        status_badge = '<span class="badge badge-success">✅ Validé Bac+2/3</span>' if is_ok else '<span class="badge badge-danger">❌ Rejeté / Non compatible</span>'
        score_class = "score-high" if eval_data["score_matching"] >= 75 else ("score-med" if eval_data["score_matching"] >= 50 else "score-low")

        stack_badges = "".join([f'<span class="badge-tech">{t}</span>' for t in eval_data["target_stack"]]) or '<span class="text-muted">Non listé</span>'

        card = f"""
        <div class="job-card {'card-retained' if is_ok else 'card-rejected'}">
          <div class="card-header">
            <div>
              <h3 class="job-title">{r["title"]}</h3>
              <div class="badges-row">
                {status_badge}
                <span class="badge {score_class}">Score : {eval_data["score_matching"]}%</span>
                <span class="badge badge-info">Durée : {eval_data["duration_months"] or "3-4"} mois</span>
                <span class="badge badge-outline">Action : {eval_data["action_recommended"]}</span>
              </div>
            </div>
            <a href="{r["url"]}" target="_blank" rel="noopener" class="btn-visit">Voir l'offre ↗</a>
          </div>
          
          <div class="verdict-box">
            <strong>Verdict :</strong> {eval_data["verdict_summary"]}
          </div>
          
          <div class="stack-row">
            <strong>Stack identifiée :</strong> {stack_badges}
          </div>
          
          <details class="job-details">
            <summary>Afficher l'extrait de l'annonce</summary>
            <div class="excerpt-text">{r["content"].replace('\n', '<br>')}</div>
          </details>
        </div>
        """
        cards_html.append(card)

    cards_str = "\n".join(cards_html)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Stage Hunter — Dashboard Sourcing</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #64748b;
      --primary: #0284c7;
      --border: #e2e8f0;
      --success: #16a34a;
      --danger: #dc2626;
      --warning: #d97706;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 32px 20px;
    }}
    .container {{
      max-width: 1000px;
      margin: 0 auto;
    }}
    .header {{
      background: var(--card-bg);
      border-radius: 12px;
      padding: 24px;
      border: 1px solid var(--border);
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      margin-bottom: 24px;
    }}
    h1 {{ margin: 0 0 8px 0; font-size: 22pt; color: #0369a1; }}
    .subtitle {{ color: var(--text-muted); font-size: 11pt; margin-bottom: 16px; }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .stat-card {{
      background: #f1f5f9;
      border-radius: 8px;
      padding: 12px 16px;
      text-align: center;
    }}
    .stat-card .val {{ font-size: 20pt; font-weight: 800; color: #0284c7; }}
    .stat-card .lbl {{ font-size: 9pt; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }}
    .job-card {{
      background: var(--card-bg);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 16px;
      border: 1px solid var(--border);
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      transition: transform 0.15s, box-shadow 0.15s;
    }}
    .job-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }}
    .card-retained {{ border-left: 5px solid var(--success); }}
    .card-rejected {{ border-left: 5px solid var(--danger); opacity: 0.75; }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }}
    .job-title {{ margin: 0 0 8px 0; font-size: 14pt; }}
    .badges-row {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 8pt;
      font-weight: 700;
    }}
    .badge-success {{ background: #dcfce7; color: var(--success); }}
    .badge-danger {{ background: #fee2e2; color: var(--danger); }}
    .badge-info {{ background: #e0f2fe; color: #0284c7; }}
    .badge-outline {{ border: 1px solid var(--border); color: var(--text-muted); }}
    .score-high {{ background: #dcfce7; color: #15803d; }}
    .score-med {{ background: #fef3c7; color: #b45309; }}
    .score-low {{ background: #fee2e2; color: #b91c1c; }}
    .badge-tech {{
      background: #f1f5f9;
      color: #334155;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 8pt;
      font-weight: 600;
      margin-right: 4px;
    }}
    .btn-visit {{
      background: #0284c7;
      color: #ffffff;
      text-decoration: none;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 9pt;
      font-weight: 700;
      white-space: nowrap;
    }}
    .btn-visit:hover {{ background: #0369a1; }}
    .verdict-box {{
      margin: 14px 0 10px 0;
      padding: 10px 12px;
      background: #f8fafc;
      border-radius: 6px;
      font-size: 9.5pt;
      color: #334155;
      line-height: 1.4;
    }}
    .stack-row {{ font-size: 9pt; margin-bottom: 10px; }}
    details summary {{
      cursor: pointer;
      font-size: 8.5pt;
      color: var(--primary);
      margin-top: 8px;
    }}
    .excerpt-text {{
      margin-top: 10px;
      padding: 10px;
      background: #f1f5f9;
      border-radius: 6px;
      font-size: 8.5pt;
      color: #475569;
      line-height: 1.4;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎯 Stage Hunter — Pipeline Dashboard</h1>
      <div class="subtitle">Analyse automatique &amp; tamisage des offres de stage (Candidat : Ezéchiel DJEBE — Bac+2 ISEP)</div>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="val">{total}</div>
          <div class="lbl">Offres scannées</div>
        </div>
        <div class="stat-card">
          <div class="val" style="color: var(--success);">{retained}</div>
          <div class="lbl">Qualifiées Bac+2/3</div>
        </div>
        <div class="stat-card">
          <div class="val" style="color: var(--danger);">{rejected}</div>
          <div class="lbl">Rejetées (Bac+5/PFE)</div>
        </div>
      </div>
    </div>

    <div class="job-list">
      {cards_str}
    </div>
  </div>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Traitement par lot Stage-Hunter")
    parser.add_argument("--file", "-f", type=str, help="Chemin vers le fichier Markdown issu de l'extension")
    args = parser.parse_args()

    # Détection automatique du fichier d'entrée si non spécifié
    input_file = None
    if args.file:
        input_file = Path(args.file)
    else:
        raw_dir = PROJECT_ROOT / "output" / "raw_markdown"
        md_files = sorted(raw_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if md_files:
            input_file = md_files[0]
            print(f"[INFO] Utilisation du dernier export trouvé : {input_file.name}")
        else:
            # Recherche dans Téléchargements
            downloads_dir = Path.home() / "Downloads"
            dl_files = sorted(downloads_dir.glob("offres_prefiltrees_*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
            if dl_files:
                input_file = dl_files[0]
                print(f"[INFO] Export détecté dans Téléchargements : {input_file.name}")
            else:
                print("[ERREUR] Aucun fichier Markdown d'offres trouvé.")
                print("➡️ Déposez un fichier dans output/raw_markdown/ ou spécifiez-le avec --file.")
                return

    if not input_file.exists():
        print(f"[ERREUR] Le fichier '{input_file}' est introuvable.")
        return

    print(f"📖 Lecture du fichier : {input_file}")
    content = input_file.read_text(encoding="utf-8")
    offers = parse_extension_markdown(content)
    print(f"🔍 {len(offers)} offre(s) détectée(s) dans le fichier.\n")

    results = []
    for idx, offer in enumerate(offers, 1):
        print(f"[{idx}/{len(offers)}] Traitement : {offer['title'][:50]}...")
        # 1. Tamis 1 Regex de sécurité
        filter_res = filter_offer_text(offer["title"], offer["content"])
        if filter_res["is_rejected"]:
            print(f"  ❌ Rejet immédiat Tamis 1 : {filter_res['rejection_reason']}")
            eval_res = {
                "is_compatible_bac2_3": False,
                "duration_months": None,
                "score_matching": 0,
                "target_stack": filter_res["stack"],
                "verdict_summary": f"Exclu par Tamis 1 Regex ({filter_res['rejection_reason']}).",
                "action_recommended": "REJETER"
            }
        else:
            # 2. Tamis 2 LLM
            evaluation = evaluate_offer_with_llm(offer["title"], offer["content"])
            eval_res = evaluation.model_dump()
            print(f"  {'✅' if eval_res['is_compatible_bac2_3'] else '⚠️'} Verdict LLM : {eval_res['action_recommended']} (Score: {eval_res['score_matching']}%)")

        results.append({
            "title": offer["title"],
            "url": offer["url"],
            "content": offer["content"],
            "evaluation": eval_res
        })

    # Génération du rapport de synthèse
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dashboard_path = PROJECT_ROOT / "output" / "dashboards" / f"dashboard_{timestamp}.html"
    generate_html_dashboard(results, dashboard_path)

    # Sauvegarde JSON
    json_path = PROJECT_ROOT / "output" / "dashboards" / f"results_{timestamp}.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n🎉 Traitement terminé avec succès !")
    print(f"📊 Tableau de bord généré : {dashboard_path}")
    print(f"🗂️ Données brutes JSON : {json_path}")


if __name__ == "__main__":
    main()
