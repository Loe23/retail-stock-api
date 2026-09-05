from fastapi import FastAPI, Depends, Query, Security, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import datetime, timezone
import uvicorn

# ==========================================
# 1. AUTHENTIFICATION PAR CLÉ API
# ==========================================
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

VALID_KEYS = {
    "demo_retail_2026": {"client": "Client Demo", "plan": "Starter"},
    "auchan_issy_prod": {"client": "Auchan Issy", "plan": "Premium"},
}

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante (Utilisez : demo_retail_2026)"
        )
    return VALID_KEYS[api_key]

# ==========================================
# 2. MODÈLES DE DONNÉES
# ==========================================
class StatutRupture(str, Enum):
    RUPTURE_CONFIRMEE = "RUPTURE_CONFIRMEE"
    RUPTURE_IMMINENTE = "RUPTURE_IMMINENTE"
    A_SURVEILLER = "A_SURVEILLER"
    OPTIMAL = "OPTIMAL"
    SURSTOCK = "SURSTOCK_OU_ANOMALIE"

class Produit(BaseModel):
    sku: str
    designation: str
    rayon: str
    fournisseur: str
    stock_magasin: int
    stock_reserve: int
    ventes_moy_jour: float
    delai_livraison_jours: int
    prix_vente_unitaire: float
    ca_journalier_moyen: float

# ==========================================
# 3. DONNÉES DU MAGASIN (MOCK RETAIL)
# ==========================================
PRODUITS = [
    Produit(sku="LIQ-001", designation="Lait Demi-Écrémé 1L x6", rayon="Liquides", fournisseur="Lactalis", stock_magasin=4, stock_reserve=0, ventes_moy_jour=28, delai_livraison_jours=2, prix_vente_unitaire=5.49, ca_journalier_moyen=153.72),
    Produit(sku="LIQ-002", designation="Eau Cristalline 1.5L x6", rayon="Liquides", fournisseur="Cristalline", stock_magasin=45, stock_reserve=120, ventes_moy_jour=35, delai_livraison_jours=3, prix_vente_unitaire=2.99, ca_journalier_moyen=104.65),
    Produit(sku="LIQ-003", designation="Coca-Cola 1.5L", rayon="Liquides", fournisseur="Coca-Cola", stock_magasin=0, stock_reserve=0, ventes_moy_jour=22, delai_livraison_jours=2, prix_vente_unitaire=1.89, ca_journalier_moyen=41.58),
    Produit(sku="EPS-001", designation="Riz Basmati 1kg", rayon="Épicerie Salée", fournisseur="Taureau Ailé", stock_magasin=2, stock_reserve=0, ventes_moy_jour=15, delai_livraison_jours=3, prix_vente_unitaire=2.79, ca_journalier_moyen=41.85),
    Produit(sku="EPS-002", designation="Pâtes Barilla Spaghetti 500g", rayon="Épicerie Salée", fournisseur="Barilla", stock_magasin=60, stock_reserve=80, ventes_moy_jour=18, delai_livraison_jours=4, prix_vente_unitaire=1.49, ca_journalier_moyen=26.82),
    Produit(sku="FRA-001", designation="Yaourt Danone Nature x4", rayon="Frais", fournisseur="Danone", stock_magasin=6, stock_reserve=0, ventes_moy_jour=20, delai_livraison_jours=1, prix_vente_unitaire=2.19, ca_journalier_moyen=43.80),
    Produit(sku="FRA-002", designation="Beurre Doux Président 250g", rayon="Frais", fournisseur="Président", stock_magasin=15, stock_reserve=20, ventes_moy_jour=10, delai_livraison_jours=2, prix_vente_unitaire=2.89, ca_journalier_moyen=28.90),
    Produit(sku="BLG-001", designation="Pain de Mie Complet", rayon="Boulangerie", fournisseur="Jacquet", stock_magasin=5, stock_reserve=0, ventes_moy_jour=14, delai_livraison_jours=1, prix_vente_unitaire=1.99, ca_journalier_moyen=27.86),
    Produit(sku="DPH-001", designation="Papier Toilette Lotus x12", rayon="Hygiène", fournisseur="Lotus", stock_magasin=30, stock_reserve=50, ventes_moy_jour=12, delai_livraison_jours=4, prix_vente_unitaire=6.99, ca_journalier_moyen=83.88),
    Produit(sku="FLG-001", designation="Bananes Cavendish 1kg", rayon="Fruits & Légumes", fournisseur="Chiquita", stock_magasin=8, stock_reserve=0, ventes_moy_jour=30, delai_livraison_jours=1, prix_vente_unitaire=1.99, ca_journalier_moyen=59.70),
]

# ==========================================
# 4. MOTEUR DE CALCUL DE RUPTURE
# ==========================================
def analyser_produit(p: Produit):
    stock_total = p.stock_magasin + p.stock_reserve
    couverture = stock_total / p.ventes_moy_jour if p.ventes_moy_jour > 0 else 999

    if couverture <= 0:
        statut = StatutRupture.RUPTURE_CONFIRMEE
        perte = p.ca_journalier_moyen
        action = f"URGENT : Commander {int(p.ventes_moy_jour * 3)} unités (Fournisseur: {p.fournisseur})"
    elif couverture <= p.delai_livraison_jours:
        statut = StatutRupture.RUPTURE_IMMINENTE
        perte = p.ca_journalier_moyen * 0.5
        action = f"Commander avant demain ({p.delai_livraison_jours}j de délai)"
    elif couverture <= p.delai_livraison_jours * 1.5:
        statut = StatutRupture.A_SURVEILLER
        perte = 0.0
        action = f"Surveiller : {couverture:.1f}j de stock restant"
    else:
        statut = StatutRupture.OPTIMAL
        perte = 0.0
        action = "Stock optimal"

    return {
        "sku": p.sku,
        "designation": p.designation,
        "rayon": p.rayon,
        "stock_total": stock_total,
        "couverture_jours": round(couverture, 2),
        "statut": statut.value,
        "perte_ca_estimee_jour": round(perte, 2),
        "action_recommandee": action
    }

# ==========================================
# 5. APPLICATION FASTAPI & ROUTES
# ==========================================
app = FastAPI(
    title="Retail Anti-Rupture API",
    description="API de pilotage des ruptures de stock en temps réel",
    version="1.0.0"
)

@app.get("/")
def home():
    return {"message": "Retail Anti-Rupture API en ligne", "docs": "/docs"}

@app.get("/v1/health")
def health():
    return {"status": "healthy", "produits_suivis": len(PRODUITS)}

@app.get("/v1/stock/overview")
def overview(client: dict = Depends(verify_api_key)):
    analyses = [analyser_produit(p) for p in PRODUITS]
    ruptures = [a for a in analyses if a["statut"] in ("RUPTURE_CONFIRMEE", "RUPTURE_IMMINENTE")]
    perte_totale = sum(a["perte_ca_estimee_jour"] for a in analyses)

    return {
        "client": client["client"],
        "total_references": len(PRODUITS),
        "produits_en_alerte": len(ruptures),
        "perte_ca_journaliere_estimee": f"{round(perte_totale, 2)} €",
        "top_urgences": sorted(ruptures, key=lambda x: x["perte_ca_estimee_jour"], reverse=True)
    }

@app.get("/v1/stock/alerts")
def alerts(client: dict = Depends(verify_api_key)):
    analyses = [analyser_produit(p) for p in PRODUITS]
    alertes = [a for a in analyses if a["statut"] != "OPTIMAL"]
    return {
        "client": client["client"],
        "nb_alertes": len(alertes),
        "alertes": sorted(alertes, key=lambda x: x["perte_ca_estimee_jour"], reverse=True)
    }

# ==========================================
# 6. DÉMARRAGE DU SERVEUR
# ==========================================
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)