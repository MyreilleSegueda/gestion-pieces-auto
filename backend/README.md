# Backend Django et API REST

## Installation locale

Depuis la racine du projet, crée un environnement virtuel et installe les dépendances :

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Depuis la racine du dépôt, copie `.env.example` en `.env` et renseigne les
variables locales. `python-dotenv` charge ce fichier; les variables système
existantes restent prioritaires. Le rôle PostgreSQL utilisé pour les tests doit
avoir le droit de créer une base temporaire. PostgreSQL reste le moteur
configuré ; aucune base métier n'est créée ou remplacée automatiquement.

```powershell
backend\.venv\Scripts\python.exe backend\manage.py check
backend\.venv\Scripts\python.exe backend\manage.py test accounts inventory utilisateurs clients fournisseurs sales invoicing reports caisse store_settings
backend\.venv\Scripts\python.exe backend\manage.py runserver
```

`POST /api/auth/mot-de-passe/` permet à l'utilisateur connecté de changer son
propre mot de passe après vérification de l'ancien. Un Administrateur peut
réinitialiser celui d'un autre utilisateur via
`POST /api/utilisateurs/{id}/reinitialiser-mot-de-passe/`. Les deux parcours
utilisent les validateurs natifs Django et ne renvoient jamais le secret.
Aucune récupération autonome par e-mail ou SMS n'est active; l'utilisateur
ayant perdu son mot de passe doit contacter l'Administrateur.

Les permissions métier sont accordées par rôle de groupe, conformément à
`accounts/role_permissions.py`. `is_staff` seul n'accorde aucun accès API
métier; seul un superuser constitue un accès administratif général. Les listes
et exports vérifient également le module pour lequel l'utilisateur possède un
droit de lecture.

Les 100 tests passent sur la base PostgreSQL temporaire créée par Django pour
les tests. La base métier n'est pas utilisée par cette suite.

## Encaissements, remboursements et clôtures

Les POST `/api/encaissements/` et `/api/remboursements/` exigent un en-tête
`Idempotency-Key` contenant un UUID. Une nouvelle tentative avec la même clé et
le même contenu renvoie l'enregistrement existant ; reutiliser la clé avec un
contenu différent renvoie `409 Conflict`. Les anciennes lignes d'encaissement
gardent une clé `NULL`.

Les remboursements sont demandes sur un encaissement, avec montant, motif et
mode. Les statuts `EN_ATTENTE`, `AUTORISE`, `REFUSE` et `EXECUTE` distinguent la
demande, la décision et l'exécution effective. Seul un Administrateur peut
autoriser/refuser. L'exécution externe n'est pas automatisée : une confirmation
autorisée doit fournir la référence du justificatif et l'utilisateur/datetime
sont historisés. Seuls les remboursements `EXECUTE` affectent les soldes nets.
Le reçu est lu via `GET /api/encaissements/{id}/recu/` ; cette lecture et sa
réimpression ne créent pas de paiement.

`POST /api/clotures-caisse/` clôture la journée courante selon le fuseau
`TIME_ZONE` de Django (`Africa/Ouagadougou`). Il accepte facultativement un objet
`comptage`, avec des montants physiques par code de mode de paiement. La clôture
est unique et immuable ; elle conserve encaissements bruts, remboursements
exécutés, montant théorique net, comptage et écart. Après la clôture, les
encaissements et remboursements exécutés pour cette journée sont refusés.

## Retours, annulations et achats fournisseurs

`POST /api/retours-ventes/` enregistre une demande de retour partiel ou total
avec `vente`, `motif`, `type_operation: "RETOUR"` et ses lignes
`ligne_vente`/`quantite`. Les quantités en attente et autorisées sont réservées
pour empêcher un retour supérieur aux quantités vendues. Les demandes de
retour/annulation sont autorisées ou refusées par un Administrateur via
`/api/retours-ventes/{id}/autoriser/` ou `/refuser/`. L'autorisation demande
explicitement `remise_en_stock` et produit au plus un mouvement `RETOUR` par
ligne. L'annulation validée est tracée sans supprimer la vente/la facture;
les remboursements sont créés séparément comme demandes en attente. Aucun
paiement externe n'est supposé réalisé.

Un achat fournisseur est créé à `POST /api/achats-fournisseurs/` avec le
fournisseur et des lignes historisées (pièce, quantité, prix d'achat). Le stock
ne change qu'après réception physique via
`POST /api/achats-fournisseurs/{id}/recevoir/`. La réception est
transactionnelle, traçable et idempotente. Commandes à terme, dettes et
règlements fournisseurs ne sont pas inclus.

## Exports

`GET /api/rapports/export/{type}/?export_format=xlsx|pdf` génère un vrai
classeur Excel ou un document PDF. Types disponibles : `factures`,
`encaissements`, `remboursements`, `stock`, `mouvements`, `ventes`, `retours`,
`achats-fournisseurs` et `indicateurs`. Filtres : `date_debut`, `date_fin`,
`piece`, `utilisateur` et `type_mouvement` selon le jeu de données. Le rôle
doit avoir un accès lecture/gestion au module correspondant. La limite est de
50 000 lignes par export. L'en-tête PDF reprend l'identité magasin configurée.

## Migrations et sauvegardes

Les migrations `sales/0002`, `caisse/0002` et `fournisseurs/0002` sont
additives. Avant toute application, confirme la cible PostgreSQL, crée et
vérifie une sauvegarde, puis examine le plan :

```powershell
backend\.venv\Scripts\python.exe backend\manage.py showmigrations
pg_dump --format=custom --file=gestion_pieces_auto.dump --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER $env:POSTGRES_DB
backend\.venv\Scripts\python.exe backend\manage.py migrate --plan
```

Le dump PostgreSQL ne contient pas les fichiers du magasin. Si `backend\media`
existe et contient des fichiers, sauvegarde-les séparément hors du dépôt :

```powershell
if (Test-Path backend\media) {
    $mediaRoot = (Resolve-Path backend\media).Path
    Compress-Archive -Path (Join-Path $mediaRoot '*') -DestinationPath store-media.zip -Force
    Get-FileHash gestion_pieces_auto.dump, store-media.zip -Algorithm SHA256
} else {
    Write-Output 'Aucun dossier MEDIA_ROOT : aucun média à archiver.'
}
```

Pour tester les fichiers médias, extrais l'archive dans un dossier de
validation distinct, compare les empreintes avec la sauvegarde, puis vérifie
les fichiers attendus avant toute restauration vers `MEDIA_ROOT`. Ne restaure
pas directement au-dessus d'un répertoire de production non sauvegardé :

```powershell
Expand-Archive -LiteralPath store-media.zip -DestinationPath .\restore-media-validation -Force
Get-ChildItem .\restore-media-validation -Recurse -File
```

Pour vérifier une restauration sans remplacer la base utilisée, restaure l'archive dans une base de test distincte :

```powershell
createdb --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER gestion_pieces_auto_restore_test
pg_restore --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER --dbname=gestion_pieces_auto_restore_test gestion_pieces_auto.dump
```

Les outils PostgreSQL demanderont le mot de passe si nécessaire. Une archive
custom PostgreSQL de 66 904 octets a été restaurée dans la base de validation
distincte `gestion_pieces_auto_restore_check_20261102`, puis les migrations
additives ont été appliquées uniquement à cette copie. La copie initiale
contenait 2 utilisateurs, 1 configuration magasin, 1 facture et les paiements
historiques de 2 000 et 2 500 FCFA (4 500 FCFA au total). Ces deux paiements
ont ensuite été retrouvés dans les contrôles navigateur ; les opérations de
validation ont ajouté des données de test à cette copie uniquement.

La restauration n'a pas ciblé la base métier. `MEDIA_ROOT` était configuré
vers `backend\media`, mais le dossier et ses fichiers étaient absents au moment
du contrôle; il n'existait donc pas d'archive média à restaurer. Les tests
`store_settings` couvrent le stockage et la préservation du logo. La restauration
de médias réels et leur inclusion dans une sauvegarde de production restent à
valider dès qu'un fichier média existe dans cet environnement.

En production, définir `DJANGO_DEBUG=False`, fournir une nouvelle `DJANGO_SECRET_KEY`, des identifiants PostgreSQL via variables d'environnement et servir l'application derrière HTTPS.