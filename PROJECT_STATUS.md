# Etat du projet IdentifySecure

Etat de l'audit et du code au 29 octobre 2026. Le fichier `CAHIER_DES_CHARGES.md` n'est pas present dans le workspace ; l'audit utilise le cahier joint dans la conversation. L'architecture Django REST + React/Vite est conservee. Aucun template Django n'a ete cree.

## Comparaison exigences / implementation

| Domaine | Etat code | Priorite / dependances | Reste / decision |
|---|---|---|---|
| Authentification et roles | Connexion, session restauree, deconnexion CSRF ; dernier administrateur protege par verrou transactionnel et test PostgreSQL concurrent. Matrice des droits API et permissions Django consultable en lecture seule depuis Utilisateurs et roles. | P0, socle des pages protegees | Confirmer la matrice cible et les exceptions `is_staff`. |
| Pieces et categories | API, modele et vues React : CRUD hors suppression definitive, recherche, seuil, statut actif ; prix negatif refuse par l'API et `full_clean()` ; suppression d'une categorie referencee renvoie 409 sans perte de donnees. La quantite ne se modifie que par mouvement. | P1, socle du stock et des ventes | Tester les contraintes et la concurrence sur les donnees PostgreSQL cible. |
| Mouvements et inventaires | Entree, sortie, retour, correction y compris stock zero ; auteur, historique non supprimable, cle d'idempotence et anti-stock negatif. | P1, depend du catalogue | La cle `Idempotency-Key` est obligatoire pour les POST mouvement. Inventaire physique multi-utilisateur a valider sur PostgreSQL. |
| Fournisseurs | Repertoire de coordonnees, edition et desactivation via API et React. | P1 partiel, depend du stock | Le cahier ne tranche pas entre simples entrees et module complet achats/commandes/dettes. Le module complet n'est pas implemente. |
| Clients | Repertoire nom, telephone, adresse, edition et desactivation ; association facultative dans une vente. | P2, depend des ventes | Pas d'historique client ni de solde a recevoir tant que le credit n'est pas valide. |
| Ventes | Brouillons multi-lignes modifiables, prix figes sur lignes conservees, validation transactionnelle avec stock/facture atomiques ; validation/annulation simultanees testees sur PostgreSQL. | P2, depend du catalogue et du stock | Pas de remise, retour/avoir, vente a credit ou paiement. Ces regles sont a valider. |
| Facturation | Facture unique en lecture seule generee avec la vente validee ; valeurs issues des prix figes ; consultation et impression navigateur/PDF. | P2, depend d'une vente validee | Coordonnees legales, devise, format reglementaire, numerotation et procedure d'annulation a valider. Paiements et soldes ne sont pas inclus. |
| Caisse et paiements | Absents. | P3, depend des regles de paiement et de vente | Modes de paiement, paiements partiels, remboursement, depenses et ouverture/cloture a confirmer. |
| Tableau de bord et rapports | Dashboard et page Rapports React relies aux KPI stock, ventes validees, chiffre d'affaires filtre par dates et mouvements recents ; rafraichissement apres mouvement/vente. API admin expose les droits API effectifs et les permissions Django assignees par groupe. | P3, depend des donnees stock/ventes | Encaissements, impayes et caisse absents ; exports PDF/Excel non implementes. |
| Securite et livraison | Secrets par variables d'environnement, PostgreSQL conserve, roles verifies, tests, guide backend/frontend et procedure de sauvegarde. Archive pre-migration creee et verifiee ; migrations appliquees a la base locale de developpement. | P0 pour la suite du developpement | Restauration de l'archive non executee ; parcours navigateur authentifie non execute ; sauvegarde periodique et configuration des comptes/groupes restent a formaliser. |

## Migrations de developpement

Les migrations suivantes ont ete appliquees a la base PostgreSQL locale `gestion_pieces_auto` le 29 octobre 2026, apres creation et verification d'une archive pre-migration :

- `inventory/0003_mouvementstock_utilisateur`
- `inventory/0004_mouvementstock_idempotency_key`
- `clients/0001_initial`
- `fournisseurs/0001_initial`
- `sales/0001_initial`
- `invoicing/0001_initial`

La configuration reste sur PostgreSQL. Le fichier `backend/db.sqlite3` n'a pas ete utilise ni remplace. Les migrations ajoutees creent des tables ou des champs et n'ont pas supprime de table ni de colonne. Les compteurs apres migration sont : 2 categories, 2 pieces, 2 mouvements ; clients, fournisseurs, ventes et factures sont vides.

## Decisions a faire valider

- La devise et les coordonnees legales du magasin pour les factures.
- La regle de numerotation, conservation et annulation de facture.
- Ventes a credit, paiements partiels et modes d'encaissement autorises.
- Retours/avoirs apres validation et autorisation d'annulation.
- Remises, modification des prix et roles autorises.
- Gestion des commandes, receptions, dettes et paiements fournisseurs.
- Ouverture/cloture caisse, remboursements et depenses.
- Nombre de magasins/emplacements et rapports/export prioritaires.

## Verification executee

- `manage.py check` : passe.
- `manage.py makemigrations --check --dry-run` : aucune migration manquante.
- 57 tests Django par labels d'applications : passent sur la base PostgreSQL temporaire creee par Django, y compris les tests concurrents validation/annulation et retrait du dernier role administrateur.
- Sur la base locale : `check`, verification des migrations, smoke GET sur dix routes API et proxy React vers CSRF (200, cookie pose) passes.
- `npm run lint --prefix frontend` : passe.
- `npm run build --prefix frontend` : passe.
- Parcours navigateur authentifie multi-role et restauration effective de l'archive : pas encore executes. Les tests fonctionnels utilisent la base temporaire de Django, pas les donnees metier.
