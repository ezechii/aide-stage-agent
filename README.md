# 🎯 Stage Hunter Agent (Antigravity Pipeline)

Pipeline hybride optimisé (Zéro-Token Waste) pour l'aspiration, le tamisage et la qualification d'offres de stages techniques (Bac+2 / Bac+3, 3 à 4 mois, Python / C++ / Linux / Traitement du signal / Embarqué).

---

## 🏗️ Architecture du projet

```text
stage-hunter-agent/
│
├── .env.example                 # Modèle des variables d'environnement
├── .env                         # Configuration locale (clé Gemini API)
├── README.md                    # Documentation complète
├── requirements.txt             # Dépendances Python
│
├── extension/                   # Extension de navigateur locale (Manifest V3)
│   ├── manifest.json            # Déclaration Manifest V3
│   ├── popup.html               # Interface utilisateur
│   ├── popup.js                 # Extraction in-page, Tamis 1 Regex, export MD
│   └── styles.css               # Design minimaliste
│
├── core/                        # Moteur d'analyse & qualification
│   ├── __init__.py
│   ├── filters.py               # Tamis 1 (Regex négatifs Bac+5/6 mois, critères positifs)
│   ├── parser.py                # Parseur HTML & décodeur de l'export Markdown
│   └── llm_evaluator.py         # Tamis 2 (Validation structurée Pydantic via Google GenAI)
│
├── cli/                         # Interface en ligne de commande
│   ├── __init__.py
│   └── run_batch.py             # Script de qualification par lot & génération dashboard
│
└── output/                      # Artefacts générés
    ├── .gitkeep
    ├── raw_markdown/            # Fichiers bruts issus de l'extension
    └── dashboards/              # Rapports HTML interactifs
```

---

## 🚀 Installation & Démarrage

### 1. Activer l'environnement virtuel Python

```bash
# Dans le dossier stage-hunter-agent :
.\venv\Scripts\Activate.ps1
```

### 2. Configurer la clé Gemini

Éditez le fichier `.env` et ajoutez votre clé d'API Google Gemini :
```env
GEMINI_API_KEY=votre_cle_api_ici
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🌐 Charger l'extension dans Chromium / Brave

1. Ouvrez votre navigateur Chromium ou Brave.
2. Accédez à la page des extensions : `chrome://extensions` ou `brave://extensions`.
3. Activez le **Mode développeur** (en haut à droite).
4. Cliquez sur **Charger l'extension non empaquetée** (*Load unpacked*).
5. Sélectionnez le dossier :  
   `C:\Users\djebe\.gemini\antigravity\scratch\stage-hunter-agent\extension`
6. L'icône **Stage Hunter** apparaît dans la barre d'outils !

---

## 🔄 Flux d'utilisation

1. **Navigation :** Rendez-vous sur un portail carrières (ex: Thales, Safran, Airbus, etc.) avec vos résultats de recherche.
2. **Extraction :** Cliquez sur l'extension puis sur `⚡ Aspirer & Filtrer la page`.
   - L'extension élimine automatiquement les Bac+5 / 6 mois (Tamis 1).
   - Un fichier `offres_prefiltrees_TIMESTAMP.md` est téléchargé.
3. **Qualification LLM & Dashboard :**
   Placez le fichier dans `output/raw_markdown/` (ou laissez le script le trouver automatiquement dans `Downloads/`) et lancez :
   ```bash
   python cli/run_batch.py
   ```
4. **Consultation :** Le script ouvre ou génère un tableau de bord HTML interactif dans `output/dashboards/` avec liens directs et scores de pertinence.
