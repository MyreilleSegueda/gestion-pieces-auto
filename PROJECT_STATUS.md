# Etat du projet IdentifySecure

Etat de l'audit et du code au 2 novembre 2026. Le fichier `CAHIER_DES_CHARGES.md` n'est pas present dans le workspace ; l'audit utilise le cahier joint dans la conversation. L'architecture Django REST + React/Vite est conservee. Aucun template Django n'a ete cree.

## Comparaison exigences / implementation

| Domaine | Etat code | Priorite / dependances | Reste / decision |
|---|---|---|---|
| Authentification et roles | Connexion, session restauree, deconnexion CSRF ; dernier administrateur protege par verrou transactionnel et test PostgreSQL concurrent. Matrice des droits API par role ; `is_staff` seul ne donne plus de droits metier. Changement de mot de passe utilisateur, reinitialisation admin pour un autre compte, sans exposition de secret. | P0, socle des pages protegees | Recuperation autonome oubliee non activee sans infrastructure d'identite; contacter un Administrateur. |
| Pieces et categories | API, modele et vues React : CRUD hors suppression definitive, recherche, seuil, statut actif ; prix negatif refuse par l'API et `full_clean()` ; suppression d'une categorie referencee renvoie 409 sans perte de donnees. La quantite ne se modifie que par mouvement. | P1, socle du stock et des ventes | Tester les contraintes et la concurrence sur les donnees PostgreSQL cible. |
| Mouvements et inventaires | Entree, sortie, retour, correction y compris stock zero ; auteur, historique non supprimable, cle d'idempotence et anti-stock negatif. | P1, depend du catalogue | La cle `Idempotency-Key` est obligatoire pour les POST mouvement. Inventaire physique multi-utilisateur a valider sur PostgreSQL. |
| Fournisseurs | Repertoire, achats multi-articles historises et reception explicite. Le stock ne change qu'a la reception, via des mouvements `ENTREE` tracables et idempotents. | P1, depend du stock | Commandes a terme, dettes et paiements fournisseurs restent des extensions non implementees. |
| Clients | Repertoire nom, telephone, adresse, edition et desactivation ; association facultative dans une vente. | P2, depend des ventes | Pas d'historique client ni de solde a recevoir tant que le credit n'est pas valide. |
| Ventes | Brouillons multi-lignes, validation transactionnelle, demandes de retour total/partiel et d'annulation avec approbation admin, controles de quantite, mouvements stock une seule fois et historique conserve. | P2, depend du catalogue et du stock | Remboursement financier d'un retour reste soumis a une approbation et a une confirmation d'execution separees. |
| Facturation | Factures en lecture seule, soldes et avoirs; impression et exports PDF/XLSX reels avec identite courante du magasin. | P2, depend d'une vente validee | L'identite magasin imprimee utilise la configuration courante (pas de snapshot historique). Coordonnees legales et numerotation reglementaire restent a valider. |
| Caisse et paiements | Encaissements idempotents, recus, remboursements en statuts demande/autorise/refuse/execute et clotures quotidiennes. Seuls les remboursements executes affectent les montants nets. L'execution externe exige une reference de justificatif et une confirmation utilisateur. | P1, depend des factures validees | Aucun prestataire de paiement externe n'est integre. |
| Tableau de bord et rapports | KPI distinguent ventes, paiements bruts, remboursements executes, net et impayes. Exports PDF/XLSX telechargeables pour factures, recus/encaissements, remboursements, stock, mouvements, ventes, retours, achats et indicateurs; filtres dates, piece, utilisateur et type de mouvement quand pertinents. | P2, depend des donnees stock/ventes/caisse | Exports limites a 50 000 lignes par requete. |
| Parametres du magasin et documents | Configuration unique lisible ; modification admin ; logos PNG/JPEG/WebP valides (2 Mo max, dimension limitee) ; logo utilise par facture et recu ; absence de nouveau fichier conserve le logo actuel. | P1, depend de l'API magasin | Les anciennes factures sans snapshot d'identite utilisent l'identite magasin actuelle a l'impression. |
| Interface React / Vite / Tailwind | Tailwind CSS 4 integre via `@tailwindcss/vite`; styles communs harmonises pour navigation, cartes, formulaires, tableaux, boutons et alertes. Le menu lateral reste navigable sur les ecrans bas et la navigation est defilable sur mobile. Les styles d'impression existants sont conserves. Le module Parametres du magasin a une presentation dediee, avec apercu de marque, etat des droits et pied de page. | P1, frontend | Les parcours navigateur precedents ont couvert les pages et roles decrits ci-dessous. La refonte actuelle du module magasin et les formulaires de mot de passe n'ont pas ete revalidees dans une session navigateur authentifiee. |
| Securite et livraison | PostgreSQL conserve, permissions de lecture/ecriture et d'export par role pour les API metier, migrations additives, tests fonctionnels automatises. Fuseau configure sur `Africa/Ouagadougou`; aucune conversion des timestamps enregistres n'a ete effectuee. Les droits UI suivent les roles metier. | P0 avant toute migration de production | Les sauvegardes/restaurations et parcours navigateur deja effectues concernent une copie de validation, pas la production. Confirmer l'identite de la base cible avant tout deploiement. |
| Livraison responsable | README d'installation independante, modele `.env.example`, dependances Python/Node, PostgreSQL, migrations, creation du superuser et commandes de test documentes. | Pret a cloner et configurer localement | Les identifiants PostgreSQL et secrets doivent etre crees localement; aucune fixture ni donnee reelle n'est distribuee. |

## Migrations de developpement

Les migrations suivantes etaient appliquees a la base PostgreSQL locale `gestion_pieces_auto` le 29 octobre 2026, apres creation et verification d'une archive pre-migration :

- `inventory/0003_mouvementstock_utilisateur`
- `inventory/0004_mouvementstock_idempotency_key`
- `clients/0001_initial`
- `fournisseurs/0001_initial`
- `sales/0001_initial`
- `invoicing/0001_initial`

Les migrations additives `sales/0002`, `caisse/0002` et `fournisseurs/0002` creent les tables de retours, les champs de suivi des remboursements, et les modeles d'achats fournisseurs. Elles ne suppriment ni ne re-ecrivent de paiements. Lors de cette passe, aucune commande `migrate` n'a ete lancee. Les horodatages existants ne sont pas convertis; avec `USE_TZ=True`, le fuseau metier determine leur interpretation et affichage local.

La configuration reste sur PostgreSQL. Le fichier `backend/db.sqlite3` n'a pas ete utilise ni remplace. Les migrations ajoutees creent des tables ou des champs et n'ont pas supprime de table ni de colonne. Les compteurs apres migration sont : 2 categories, 2 pieces, 2 mouvements ; clients, fournisseurs, ventes et factures sont vides.

Une archive PostgreSQL custom de 66 904 octets a ete restauree dans
`gestion_pieces_auto_restore_check_20261102`, une base distincte. La copie
initiale contenait 2 utilisateurs, 1 configuration magasin, 1 facture et deux
paiements de 2 000 et 2 500 FCFA. Les migrations additives ont ete appliquees
sur cette copie seulement. Des comptes et donnees synthetiques ont ete ajoutes
a cette base pour les essais navigateur; elle ne doit pas etre confondue avec
la base metier. `MEDIA_ROOT` etait configure vers `backend/media`, mais le
dossier n'existait pas; aucune image de logo n'etait disponible a restaurer.

## Decisions a faire valider

- Les coordonnees legales, la numerotation reglementaire et la conservation des factures.
- Ventes a credit, paiements partiels et modes d'encaissement autorises.
- Retours/avoirs apres validation et autorisation d'annulation.
- Remises, modification des prix et roles autorises.
- Commandes a terme, dettes et paiements fournisseurs (les achats et receptions effectives sont implementes).
- Ouverture/cloture caisse, remboursements et depenses.
- La procedure manuelle d'execution des remboursements externes et la politique sur les pieces endommagees.
- Nombre de magasins/emplacements.

## Verification executee

- `manage.py check` et `manage.py makemigrations --check --dry-run` : passes.
- 100 tests Django : passes sur une base PostgreSQL temporaire creee par Django. Couverture ciblee des retours/annulations, matrice des permissions, absence de contournement `is_staff`, changement/reinitialisation de mot de passe, idempotence des receptions, exports PDF/XLSX et operations de caisse.
- `npm --prefix frontend run lint` et `npm --prefix frontend run build` : passes avec Tailwind CSS 4 et Vite 8.
- Tests verifies : XLSX reel lisible, PDF reel, filtre piece/utilisateur/type mouvement, refus d'export caisse pour un role Vendeur, reception fournisseur stockee une seule fois.
- Lors de la passe du 2 novembre 2026, `manage.py check`, `makemigrations --check --dry-run` et les 100 tests backend ont passe apres correction des fixtures. Le lint et le build React/Vite ont egalement passe apres l'ajout du profil mot de passe et la refonte des Parametres du magasin. Un essai navigateur isole avec session/API simulees n'a pas depasse l'ecran de verification de session; il n'est pas compte comme validation visuelle ou fonctionnelle. Les tests API couvrent les scenarii authentifie, erreur d'ancien mot de passe, mot de passe faible, compte non admin et reinitialisation admin.
- L'API refuse maintenant l'acces de lecture comme d'ecriture aux comptes sans role module, et `is_staff=True` seul ne donne pas de droits metier. Les suites testent directement la matrice et les principales API. Les donnees de production n'ont pas ete modifiees pendant cette passe.
- Parcours navigateur sur la base restauree : les 11 rubriques sont accessibles a l'Administrateur; le Caissier accede a la caisse; le Vendeur ne voit pas le menu caisse ni ses lignes apres connexion, y compris les paiements admin de 2 000 et 2 500 FCFA.
- Parcours navigateur supplementaire : le Gestionnaire de stock a charge sans erreur le tableau de bord, le catalogue, les mouvements, les fournisseurs, les ventes, les clients, les factures, les rapports et les parametres; les menus caisse et utilisateurs ne sont pas exposes.
- Facture et recu controles dans le navigateur : l'identite magasin configuree apparait sur les deux documents. Les exports navigateur ont repondu en HTTP 200 avec un vrai XLSX (MIME Excel) et un vrai PDF (signature `%PDF`).
- Les 11 pages Admin ont ete parcourues dans le navigateur a 390 px : chaque titre attendu apparait, aucune alerte d'erreur, largeur document egale a la largeur du viewport. Le Gestionnaire a aussi ouvert toutes les pages auxquelles son role a acces.
- Tests `store_settings` : 3/3 reussis, y compris televersement et conservation du logo, rejet d'image invalide et depassement de taille. Le dossier `MEDIA_ROOT` de l'environnement n'existait pas.
- Procedure d'archive/restauration media essayee sur un PNG synthetique dans un dossier temporaire : extraction archive et empreintes SHA-256 source/restauration identiques. Ce test n'est pas une restauration d'un media de production.
- Controle PostgreSQL en lecture seule le 2 novembre : `showmigrations` indique les migrations affichees comme appliquees sur la base de connexion par defaut `gestion_pieces_auto`. La passe n'a execute aucune migration. L'identite de cette base par rapport a la base de production doit etre confirmee par l'exploitant avant deploiement.
- Controle PostgreSQL en lecture seule : 2 encaissements dans la base par defaut, dont les montants 2 000 et 2 500 FCFA. Aucun paiement n'a ete ajoute, modifie ou supprime par cette passe; la suite Django a utilise sa base temporaire.
- `npm --prefix frontend audit --audit-level=moderate` : 0 vulnerabilite apres surcharge de `minimatch` en `^11.0.1`. Lint et build frontend relances apres le correctif, reussis.
- Limites restantes : le parcours navigateur ne constitue pas un test de production; aucun media/backup media et aucun compte de production n'etaient disponibles. La migration sur la base metier et la validation de la matrice de permissions finale restent sous responsabilite de l'exploitant. Les commandes fournisseurs a terme/dettes/paiements, le prestataire de remboursement et la conversion des horodatages historiques restent hors action.
