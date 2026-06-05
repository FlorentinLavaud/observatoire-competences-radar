# src/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

class FranceTravailOfferParser(BaseModel):
    """Modèle Pydantic pour parser et valider une offre brute France Travail."""
    id: str
    titre: str = Field(alias="intitule")
    description: Optional[str] = None
    code_rome: Optional[str] = Field(None, alias="romeCode")
    rome_libelle: Optional[str] = Field(None, alias="romeLibelle")
    code_naf: Optional[str] = Field(None, alias="codeNAF")
    secteur_activite: Optional[str] = Field(None, alias="secteurActivite")
    secteur_libelle: Optional[str] = Field(None, alias="secteurActiviteLibelle")
    type_contrat: Optional[str] = Field(None, alias="typeContrat")
    type_contrat_libelle: Optional[str] = Field(None, alias="typeContratLibelle")
    experience_exige: Optional[str] = Field(None, alias="experienceExige")
    offres_manque_candidats: Optional[bool] = Field(False, alias="offresManqueCandidats")
    date_creation: str = Field(alias="dateCreation")
    lieu_travail: Optional[Dict[str, Any]] = Field(None, alias="lieuTravail")

    @property
    def code_departement(self) -> Optional[str]:
        """Extrait le code département depuis l'objet lieuTravail."""
        if self.lieu_travail and "libelle" in self.lieu_travail:
            libelle = self.lieu_travail["libelle"]
            # Exemple classique de la doc : "74 - ANNECY" -> on isole "74"
            if " - " in libelle:
                return libelle.split(" - ")[0].strip()
        return None

    @property
    def nom_entreprise(self) -> Optional[str]:
        """Extrait le nom de l'entreprise si elle est renseignée."""
        # Résolu via un attribut externe car l'alias direct sur objet imbriqué est lourd
        return None

    def to_supabase_dict(self, raw_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit l'objet parsé en dictionnaire plat pour la table Supabase 'offres'."""
        # Extraction manuelle sûre des sous-objets pour l'entreprise
        entreprise_obj = raw_entry.get("entreprise", {})
        nom_acheteur = entreprise_obj.get("nom") if isinstance(entreprise_obj, dict) else None

        # Conversion propre de la date ISO en string ISO interprétable par Postgres
        try:
            dt = datetime.strptime(self.date_creation, "%Y-%m-%dT%H:%M:%SZ")
            date_parution = dt.isoformat()
        except ValueError:
            date_parution = datetime.utcnow().isoformat()

        return {
            "id": self.id,
            "source": "france_trail",
            "titre": self.titre,
            "description": self.description,
            "code_rome": self.code_rome,
            "rome_libelle": self.rome_libelle,
            "code_naf": self.code_naf,
            "secteur_activite": self.secteur_activite,
            "secteur_libelle": self.secteur_libelle,
            "nom_acheteur": nom_acheteur,
            "type_contract": self.type_contrat,
            "type_contrat_libelle": self.type_contrat_libelle,
            "experience_exige": self.experience_exige,
            "code_departement": self.code_departement,
            "offres_manque_candidats": self.offres_manque_candidats,
            "date_parution": date_parution
        }