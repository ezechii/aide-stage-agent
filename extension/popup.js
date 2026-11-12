document.getElementById('extractBtn').addEventListener('click', async () => {
  const btn = document.getElementById('extractBtn');
  const statusBox = document.getElementById('statusBox');
  btn.disabled = true;
  statusBox.textContent = "⏳ Détection des liens d'offres...";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      statusBox.textContent = "❌ Erreur : Aucun onglet actif détecté.";
      btn.disabled = false;
      return;
    }

    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: inTabScraperEngine
    }, (results) => {
      btn.disabled = false;
      if (!results || !results[0] || !results[0].result) {
        statusBox.textContent = "❌ Erreur : Impossible d'extraire le contenu de cet onglet (vérifiez que vous êtes sur une page HTTP/HTTPS).";
        return;
      }

      const { totalDetected, filteredOffers } = results[0].result;
      statusBox.textContent = `✅ Scan achevé :\n• Offres détectées : ${totalDetected}\n• Retenues (Tamis 1) : ${filteredOffers.length}\n• Rejetées (Bac+5/6 mois) : ${totalDetected - filteredOffers.length}`;

      if (filteredOffers.length > 0) {
        exportCleanMarkdown(filteredOffers);
        statusBox.textContent += `\n💾 Export Markdown téléchargé (${filteredOffers.length} offres).`;
      } else {
        statusBox.textContent += "\n⚠️ Aucune annonce compatible trouvée sur cette page.";
      }
    });
  } catch (err) {
    btn.disabled = false;
    statusBox.textContent = `❌ Erreur : ${err.message}`;
  }
});

async function inTabScraperEngine() {
  const rejectPattern = /\b(bac\s*\+?\s*(?:4\s*[/ou,-]\s*5|4|5)|master(?:\s*[12])?|m[12]|pfe|fin\s*d['’]études|dernière\s*année|5[èe]me\s*année|césure|stage\s*de\s*fin\s*d['’]études|projet\s*de\s*fin\s*d['’]études)\b/i;
  const positivePattern = /\b(bac\s*\+\s*2(?:\s*[\/+\-]\s*\+?\s*3)?|bac\s*\+\s*3|2[èe]me\s*(?:ou\s*3[èe]me\s*)?année\s*d['’ ]?école\s*d['’ ]?ingénieur|3[èe]me\s*année\s*d['’ ]?école\s*d['’ ]?ingénieur|2[èe]me\s*année|3[èe]me\s*année|[34]\s*(?:à|et|-|\/)\s*6\s*mois|3\s*à\s*4\s*mois|4\s*mois|stage\s*d['’]application|technicien|36\s*mois|3\s*ans|cycle\s*ingénieur|apprenti[e]?\s*ingénieur|contrat\s*d['’]apprentissage)\b/i;

  const links = Array.from(document.querySelectorAll('a[href]'));

  // Détection heuristique des URLs pointant vers des fiches de poste réelles
  const currentBaseUrl = window.location.href.split('?')[0];
  const excludedKeywords = [
    '/c/', '/carrieres-', '/carriere-', '-careers', '/careers', '/a-propos', '/etudiant', '/comment-postuler',
    '/equilibre', '/technologie', '/parcours', '/events', '/cookiesettings',
    '/donneespersonnelles', '/jobcart', 'privacy', 'cookie'
  ];

  const jobUrls = [...new Set(
    links
      .map(a => a.href)
      .filter(h => {
        const lower = h.toLowerCase();
        const baseH = h.split('?')[0];
        const isExcluded = excludedKeywords.some(ex => lower.includes(ex));
        return !isExcluded
          && baseH !== currentBaseUrl
          && !baseH.endsWith('/offres')
          && !baseH.endsWith('/jobs')
          && (lower.includes('/offre') || lower.includes('/job') || lower.includes('/detail') || lower.includes('/position') || lower.includes('/career'))
          && !lower.includes('#') && !lower.includes('apply') && !lower.includes('login') && !lower.includes('signup');
      })
  )];

  const filteredOffers = [];

  for (const url of jobUrls) {
    try {
      const response = await fetch(url, { credentials: 'same-origin' });
      if (!response.ok) continue;
      const htmlText = await response.text();

      const parser = new DOMParser();
      const doc = parser.parseFromString(htmlText, 'text/html');

      // Suppression des balises non pertinentes
      doc.querySelectorAll('script, style, noscript, nav, header, footer, svg, iframe').forEach(el => el.remove());

      const title = doc.querySelector('h1')?.innerText.trim() || doc.title || "Poste sans titre";
      const bodyText = doc.body?.innerText || "";

      // Rejet immédiat si l'offre est expirée ou clôturée
      const lowerBody = bodyText.toLowerCase();
      if (lowerBody.includes('a été pourvu') || lowerBody.includes('a ete pourvu') || lowerBody.includes('n\'existe pas ou plus') || lowerBody.includes('n\'est plus disponible')) {
        continue;
      }

      // TAMIS NÉGATIF : Rejet immédiat si critère d'exclusion détecté
      if (rejectPattern.test(bodyText)) {
        continue;
      }
      // Rejet 6 mois strict (en ignorant les plages compatibles "3 à 6 mois" ou "4 à 6 mois")
      const textSansPlages = bodyText.replace(/\b[34]\s*(?:à|et|-|\/)\s*6\s*mois\b/gi, "");
      if (/\b6\s*mois\b/i.test(textSansPlages)) {
        continue;
      }

      const hasBac23Explicit = positivePattern.test(bodyText);

      // Détection des technologies cibles
      const stack = [];
      ['Python', 'C\\+\\+', 'Linux', 'SQL', 'Signal', 'VHDL', 'Bash', 'C', 'Docker', 'Git', 'Électronique'].forEach(tech => {
        if (new RegExp(`\\b${tech}\\b`, 'i').test(bodyText)) {
          stack.push(tech.replace('\\', ''));
        }
      });

      // Conservation des lignes textuelles informatives sans coupure arbitraire
      const cleanParagraphs = bodyText
        .split('\n')
        .map(p => p.trim())
        .filter(p => p.length >= 4 && !/^[-*_•·#]{1,3}$/.test(p))
        .slice(0, 45)
        .join('\n');

      filteredOffers.push({
        title,
        url,
        stack: stack.join(', ') || 'Non spécifiée',
        isCertifiedBac23: hasBac23Explicit,
        content: cleanParagraphs
      });
    } catch (e) {
      console.warn("Échec récupération annonce :", url);
    }
  }

  return { totalDetected: jobUrls.length, filteredOffers };
}

function exportCleanMarkdown(offers) {
  let md = `# SOURCING STAGES & ALTERNANCES — BRUT PRÉ-FILTRÉ (TAMIS 1)\n\n`;
  md += `*Nombre d'offres qualifiées : ${offers.length}*\n\n---\n\n`;

  offers.forEach((o, i) => {
    md += `## OFFRE_${i + 1}: ${o.title}\n`;
    md += `- **URL :** ${o.url}\n`;
    md += `- **Technologies identifiées :** ${o.stack}\n`;
    md += `- **Mention explicite Bac+2/3 :** ${o.isCertifiedBac23 ? "OUI" : "À vérifier par LLM"}\n\n`;
    md += `### Extrait textuel :\n${o.content}\n\n---\n\n`;
  });

  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `offres_prefiltrees_${Date.now()}.md`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
  }, 1000);
}
