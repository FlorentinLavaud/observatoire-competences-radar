from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class FranceTravailOfferParser(BaseModel):
    """Modèle Pydantic pour parser et valider une offre brute France Travail."""
    id: str
    titre: str = Field(alias="intitule")
    description: Optional[str] = None
    code_rome: Optional[str] = Field(None, alias="romeCode")
    rome_libelle: Optional[str] = Field(None, alias="romeLibelle")
    appellation_libelle: Optional[str] = Field(None, alias="appellationLibelle")
    code_naf: Optional[str] = Field(None, alias="codeNAF")
    secteur_activite: Optional[str] = Field(None, alias="secteurActivite")
    secteur_libelle: Optional[str] = Field(None, alias="secteurActiviteLibelle")
    type_contrat: Optional[str] = Field(None, alias="typeContrat")
    type_contrat_libelle: Optional[str] = Field(None, alias="typeContratLibelle")
    nature_contrat: Optional[str] = Field(None, alias="natureContrat")
    experience_exige: Optional[str] = Field(None, alias="experienceExige")
    experience_libelle: Optional[str] = Field(None, alias="experienceLibelle")
    offres_manque_candidats: Optional[bool] = Field(False, alias="offresManqueCandidats")
    alternance: Optional[bool] = Field(False, alias="alternance")
    date_creation: Optional[str] = Field(None, alias="dateCreation")
    date_actualisation: Optional[str] = Field(None, alias="dateActualisation")
    lieu_travail: Optional[Dict[str, Any]] = Field(None, alias="lieuTravail")
    entreprise: Optional[Dict[str, Any]] = None
    nombre_postes: Optional[int] = Field(None, alias="nombrePostes")
    accessible_th: Optional[bool] = Field(False, alias="accessibleTH")
    deplacement_code: Optional[str] = Field(None, alias="deplacementCode")
    deplacement_libelle: Optional[str] = Field(None, alias="deplacementLibelle")
    qualification_code: Optional[str] = Field(None, alias="qualificationCode")
    qualification_libelle: Optional[str] = Field(None, alias="qualificationLibelle")

    @staticmethod
    def parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        formats = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @property
    def code_departement(self) -> Optional[str]:
        """Extrait le code département depuis l'objet lieuTravail."""
        if self.lieu_travail and isinstance(self.lieu_travail, dict):
            libelle = self.lieu_travail.get("libelle")
            if isinstance(libelle, str) and " - " in libelle:
                return libelle.split(" - ")[0].strip()
        return None

    @property
    def nom_entreprise(self) -> Optional[str]:
        """Extrait le nom de l'entreprise si elle est renseignée."""
        if isinstance(self.entreprise, dict):
            return self.entreprise.get("nom")
        return None

    @property
    def secteur(self) -> Optional[str]:
        """Champ secteur affichable et structuré."""
        return self.secteur_libelle or self.secteur_activite or self.code_naf

    def to_dict(self, raw_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit l'objet parsé en dictionnaire plat normalisé."""
        creation_dt = self.parse_datetime(self.date_creation)
        actualisation_dt = self.parse_datetime(self.date_actualisation) or creation_dt
        publication_date = creation_dt.date() if creation_dt else None

        return {
            "id": self.id,
            "source": "france_travail",
            "titre": self.titre,
            "description": self.description,
            "secteur": self.secteur,
            "code_naf": self.code_naf,
            "code_rome": self.code_rome,
            "rome_libelle": self.rome_libelle,
            "appellation_libelle": self.appellation_libelle,
            "type_contrat": self.type_contrat,
            "type_contrat_libelle": self.type_contrat_libelle,
            "nature_contrat": self.nature_contrat,
            "experience_exige": self.experience_exige,
            "experience_libelle": self.experience_libelle,
            "nom_acheteur": self.nom_entreprise,
            "code_departement": self.code_departement,
            "nombre_postes": self.nombre_postes,
            "accessible_th": self.accessible_th,
            "offres_manque_candidats": self.offres_manque_candidats,
            "date_publication": publication_date.isoformat() if publication_date else None,
            "date_creation": creation_dt.isoformat() if creation_dt else None,
            "date_modification": actualisation_dt.isoformat() if actualisation_dt else None,
            "raw_data": raw_entry,
        }

from pydantic import BaseModel, Field
from typing import Optional

class StatAccesEmploi(BaseModel):
    """Ligne de statistique taux d'accès à l'emploi."""
    code_rome: Optional[str] = Field(None, alias="codeRome")
    libelle_rome: Optional[str] = Field(None, alias="libelleRome")
    code_departement: Optional[str] = Field(None, alias="codeDepartement")
    libelle_departement: Optional[str] = Field(None, alias="libelleDepartement")
    annee: Optional[int] = Field(None, alias="annee")
    duree_acces_emploi: Optional[int] = Field(None, alias="dureeAccesEmploi")
    taux_acces_emploi: Optional[float] = Field(None, alias="tauxAccesEmploi")
    nb_demandeurs: Optional[int] = Field(None, alias="nbDemandeurs")
    type_sortie: Optional[str] = Field(None, alias="typeSortie")

    # champs injectés par le client
    rome_query: Optional[str] = Field(None, alias="_rome_query")
    dept_query: Optional[str] = Field(None, alias="_dept_query")
    duree_mois: Optional[int] = Field(None, alias="_duree_mois")

    class Config:
        populate_by_name = True