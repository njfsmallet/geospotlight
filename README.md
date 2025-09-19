# 🏡 GeoSpotlight - Analyse Immobilière Intelligente

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**GeoSpotlight** est un outil d'analyse immobilière géospatiale professionnel qui combine les données de proximité (OpenStreetMap) et les données transactionnelles françaises (DVF) pour générer des analyses de marché complètes et des recommandations stratégiques personnalisées.

## 🚀 Caractéristiques principales

- 📊 **Analyse DVF complète** : Données de ventes immobilières françaises officielles
- 🗺️ **Géolocalisation précise** : Commodités et services dans un rayon défini
- 📈 **Données structurées** : Prêtes pour analyse IA personnalisée
- 🤖 **IA intégrée** : Prompt optimisé pour Claude Sonnet 4 via `pb`
- 📋 **Rapports professionnels** : Analyses détaillées pour différents profils utilisateur
- ⚡ **Performance optimisée** : Gestion d'erreurs, cache, retry automatique

## 🎯 Cas d'usage

### 👨‍💼 **Pour les professionnels**
- **Agents immobiliers** : Analyses de marché instantanées pour leurs clients
- **Investisseurs** : Évaluation du potentiel ROI et des tendances
- **Promoteurs** : Études de faisabilité et positionnement prix

### 🏠 **Pour les particuliers**
- **Vendeurs** : Stratégie de pricing et timing optimal
- **Acheteurs** : Détection d'opportunités et aide à la négociation
- **Primo-accédants** : Sécurisation du projet et analyse d'environnement

## 📦 Installation

### Prérequis
- Python 3.8+
- Accès internet pour les APIs
- (Optionnel) `pb` pour l'intégration IA

### Dépendances
```bash
pip install requests geopy tabulate
```

### Installation rapide
```bash
git clone <repository-url>
cd geospotlight
chmod +x agent.py
```

## 🔧 Utilisation

### Usage de base
```bash
# Analyse interactive
./agent.py
# Saisir l'adresse : "83 Av. Raymond Aron, 91300 Massy"

# Analyse avec période personnalisée (en mois)
./agent.py --period 12

# Test d'un ID de mutation spécifique
./agent.py --test-mutation-id "2023-12345"
```

### Usage avancé avec IA
```bash
# Génération d'analyse IA complète
(echo '83 Av. Raymond Aron, 91300 Massy' | ./agent.py; cat prompt.md) | pb --smart
```

## 📊 Structure des données générées

### 1. **Analyse des commodités**
- Transport (gares, métro, bus)
- Santé (hôpitaux, pharmacies, médecins)
- Éducation (écoles, universités)
- Commerce et services

### 2. **Données transactionnelles DVF**
- Toutes les ventes dans un rayon de 350m
- Prix au m², surfaces, types de biens
- Évolution temporelle des prix
- Segmentation appartements/maisons

### 3. **Analyse statistique**
- **Moyennes et médianes** : Par segment et global
- **Évolutions temporelles** : Tendances sur la période
- **Répartition géographique** : Couverture territoriale
- **Métriques de volume** : Activité transactionnelle

## 🤖 Intégration IA avec Claude

Le fichier `prompt.md` contient un système expert optimisé pour Claude Sonnet 4 qui :

### **Rôles adaptatifs**
- 🏠 **Mode Acheteur** : Opportunités et négociation
- 💰 **Mode Vendeur** : Pricing et timing optimal
- 📈 **Mode Investisseur** : ROI et potentiel
- 🏡 **Mode Primo-accédant** : Sécurité et accompagnement

### **Système d'évaluation autonome**
- Calcul en temps réel du scoring marché A/B/C/D par l'IA
- Grille d'évaluation intégrée (volume, tendance, stabilité, qualité)
- Adaptation automatique des recommandations selon l'évaluation

## 📋 Exemples de sorties

### Analyse de base
```
🏠 GEOSPOTLIGHT REAL ESTATE ANALYSIS
📍 Location: 83 Av. Raymond Aron, 91300 Massy
🌐 Coordinates: 48.721234, 2.264567
📏 Search radius: 350 meters

================================================================================
📈 SECTION 3: STATISTICAL ANALYSIS & MARKET INSIGHTS
================================================================================

📊 MARKET OVERVIEW
• Total transactions analyzed: 77
• Valid price data points: 77
• Analysis period: 2023 - 2024

💰 FINANCIAL ANALYSIS
• Average price per m²: €4,927
• Median price per m²: €4,974
• Price range: €2,629 - €7,208
================================================================================
```

### Avec analyse IA
```
💡 DIAGNOSTIC INSTANTANÉ
Score de marché calculé : C (58/100) - Marché avec prudence recommandée

Basé sur mon analyse des 77 transactions :
• Volume d'activité : Moyen (77 transactions/24 mois)
• Tendance des prix : Légère hausse (+2.8% calculé sur période)
• Stabilité : Prix volatils (écart-type 24%)

Le pattern le plus intéressant : les appartements 3 pièces montrent une
résistance supérieure (+4.2%) vs le marché global.

Pour affiner mes recommandations, quel est votre projet : vendre, acheter,
investir, ou autre chose ?
```

## 🔧 Configuration avancée

### Paramètres personnalisables
```python
# Dans agent.py
SEARCH_RADIUS = 350        # Rayon de recherche (mètres)
DEFAULT_TIMEOUT = 30       # Timeout API (secondes)
MAX_RETRIES = 3           # Tentatives de retry
```

### Logging
Les logs sont affichés directement dans la console avec :
- Requêtes API et réponses
- Erreurs et retries
- Performance des traitements

## 📊 APIs utilisées

### 🏛️ **DVF (Demandes de Valeurs Foncières)**
- **Source** : data.gouv.fr via Cerema
- **Données** : Toutes les ventes immobilières françaises
- **Couverture** : Depuis 2014, mise à jour semestrielle
- **Limite** : 0.02° × 0.02° par requête

### 🗺️ **OpenStreetMap (Overpass API)**
- **Source** : OpenStreetMap via Overpass
- **Données** : Points d'intérêt géolocalisés
- **Couverture** : Mondiale, temps réel
- **Catégories** : Transport, santé, éducation, commerce

### 📍 **Nominatim (Géocodage)**
- **Source** : OpenStreetMap
- **Service** : Conversion adresse → coordonnées
- **Précision** : Niveau rue/bâtiment

## 🚨 Limitations et points d'attention

### Données DVF
- **Délai** : 6 mois de décalage vs transactions réelles
- **Scope** : Uniquement ventes (pas de locations)

### Géolocalisation
- **Précision** : Dépend de la qualité OSM locale
- **Rayon fixe** : 350m non modifiable (optimisé micro-quartier)

### Performance
- **APIs externes** : Dépendance à la disponibilité
- **Rate limiting** : Gestion automatique des quotas

## 🛠️ Développement

### Architecture
```
geospotlight/
├── agent.py          # Script principal optimisé
├── prompt.md         # Système expert IA
├── schema.yaml       # (Configuration future)
└── README.md         # Cette documentation
```

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- **data.gouv.fr** pour l'accès aux données DVF
- **OpenStreetMap** pour les données géospatiales
- **Anthropic** pour Claude Sonnet 4
- **Communauté Python** pour les librairies

---
