# Gestion de pièces automobiles

Application de gestion commerciale et de stock composée d'une API Django REST,
d'une base PostgreSQL et d'une interface React/Vite avec Tailwind CSS.

## Prérequis

- Windows 10/11 avec PowerShell (les commandes ci-dessous sont écrites pour Windows).
- Python 3.12 ou ultérieur compatible avec Django 6.1.
- Node.js 22.12+ (requis par Vite 8) et npm.
- PostgreSQL 15+ avec `psql` disponible pour créer la base locale.

Le dépôt ne contient aucune donnée métier réelle. Aucune base n'est créée,
réinitialisée ou remplacée automatiquement.

## Installation locale indépendante

Clone le dépôt puis exécute les commandes depuis sa racine.

### 1. Créer une base PostgreSQL locale

Depuis `psql` connecté avec un compte PostgreSQL autorisé, crée un utilisateur
et une base réservés au développement :

```sql
CREATE ROLE gestion_pieces_auto LOGIN CREATEDB PASSWORD 'choisir-un-mot-de-passe-local';
CREATE DATABASE gestion_pieces_auto OWNER gestion_pieces_auto;
```

Ne réutilise pas les identifiants d'une base partagée ou de production.

### 2. Configurer Django

Copie le modèle puis remplace ses valeurs locales :

```powershell
Copy-Item .env.example .env
```

Renseigne au minimum `DJANGO_SECRET_KEY`, `POSTGRES_USER` et
`POSTGRES_PASSWORD`. Le fichier `.env` est ignoré par Git. Django le charge
depuis la racine du dépôt; les variables déjà fournies par le système ont la
priorité.

Crée et installe l'environnement Python :

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Vérifie la configuration, puis applique les migrations uniquement à la base
locale neuve que tu viens de créer :

```powershell
backend\.venv\Scripts\python.exe backend\manage.py check
backend\.venv\Scripts\python.exe backend\manage.py migrate --plan
backend\.venv\Scripts\python.exe backend\manage.py migrate
backend\.venv\Scripts\python.exe backend\manage.py createsuperuser
```

Le compte créé par `createsuperuser` est administrateur Django et dispose des
droits applicatifs d'administration. L'administrateur peut ensuite créer les
autres comptes dans le module Utilisateurs et leur attribuer les groupes
métier. La création actuelle des comptes et l'attribution initiale de leur mot
de passe restent inchangées.

### 3. Installer et lancer React

Dans un second terminal PowerShell :

```powershell
Set-Location frontend
npm ci
npm run lint
npm run build
npm run dev
```

L'interface est disponible à `http://localhost:5173`. Vite relaie `/api` vers
Django sur `http://127.0.0.1:8000`. Pour une autre adresse locale, définir
`VITE_API_PROXY_TARGET` avant `npm run dev`.

Dans le premier terminal, démarre Django :

```powershell
backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

Le compte administrateur se connecte avec l'identifiant et le mot de passe
choisis pendant `createsuperuser`. En environnement partagé, utilise HTTPS et
configure `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` et `DJANGO_ALLOWED_HOSTS`
pour le domaine de déploiement.

## Tests et contrôles

Les tests Django utilisent une base temporaire PostgreSQL. Le rôle configuré
dans `.env` doit avoir le droit de créer cette base de test.

```powershell
backend\.venv\Scripts\python.exe backend\manage.py check
backend\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
backend\.venv\Scripts\python.exe backend\manage.py test accounts inventory utilisateurs clients fournisseurs sales invoicing reports caisse store_settings
```

Le frontend :

```powershell
Set-Location frontend
npm run lint
npm run build
```

## Rôles, accès et mots de passe

- Les droits métier reposent sur les groupes applicatifs : Administrateur,
  Responsable magasin, Gestionnaire de stock, Vendeur et Caissier.
- `is_staff` seul n'accorde aucun droit métier. Les droits Django d'accès à
  l'administration ne remplacent pas les groupes d'application. Un superuser
  constitue l'exception administrative explicite.
- L'administrateur habilité crée les comptes et attribue leurs mots de passe,
  comme auparavant. Les mots de passe ne sont jamais renvoyés par les API.
- Chaque utilisateur connecté peut changer son propre mot de passe depuis
  « Mon profil », avec vérification de l'ancien mot de passe et les validateurs
  natifs Django.
- Un Administrateur peut réinitialiser le mot de passe d'un autre utilisateur.
- Aucune récupération autonome par e-mail ou SMS n'est activée : aucune
  infrastructure d'identité de secours n'est configurée. Un utilisateur ayant
  oublié son mot de passe doit contacter l'administrateur.

## Principales règles métier

- Le fuseau horaire métier est `Africa/Ouagadougou`. Aucun horodatage historique
  n'est converti automatiquement.
- Le stock est ajusté par des mouvements traçables. Un achat ne l'augmente
  qu'après confirmation de la réception physique.
- Les ventes validées génèrent leur facture. Les factures et reçus utilisent
  les paramètres du magasin.
- Les encaissements sont idempotents. Les remboursements requièrent
  l'autorisation d'un Administrateur; leur exécution bancaire, espèces ou
  mobile money reste manuelle et nécessite une confirmation avec référence.
- Les demandes de retour et d'annulation sont historisées et soumises à
  autorisation. La remise en stock est explicitement décidée lors de
  l'autorisation d'un retour.
- Les exports PDF/XLSX appliquent les rôles et filtres disponibles.

Les commandes à terme, dettes et paiements fournisseurs, ventes à crédit et
dépenses de caisse ne font pas partie du périmètre actuel.

## Migrations et protection des données

Avant toute migration vers une base déjà utilisée :

1. Vérifie la cible avec `showmigrations` et `migrate --plan`.
2. Crée et vérifie une sauvegarde PostgreSQL hors du dépôt.
3. Examine les migrations, puis applique-les explicitement après accord du
   responsable de la base.
4. Vérifie les utilisateurs, factures et paiements après migration.

Exemple PowerShell (l'outil peut demander le mot de passe) :

```powershell
pg_dump --format=custom --file=gestion_pieces_auto.dump --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER $env:POSTGRES_DB
Get-Item .\gestion_pieces_auto.dump
```

Pour tester une restauration, crée une base de validation distincte. Ne
restaure jamais au-dessus de la base de travail ou de production :

```powershell
createdb --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER gestion_pieces_auto_restore_test
pg_restore --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER --dbname=gestion_pieces_auto_restore_test .\gestion_pieces_auto.dump
```

Les logos et médias se trouvent sous `backend\media` et doivent être archivés
séparément du dump SQL. Vérifie les deux sauvegardes avant d'envisager une
restauration.

## Données de démonstration

Aucune donnée réelle ni compte par défaut n'est fourni. Pour une présentation,
crée un environnement PostgreSQL local distinct, génère son superuser, puis
ajoute des catégories, pièces, clients et opérations de démonstration depuis
l'application avec des valeurs fictives. Ne charge pas de dump de production
dans un environnement de démonstration.

Pour l'état détaillé des fonctionnalités et de leurs limites, consulte
[PROJECT_STATUS.md](./PROJECT_STATUS.md) et [backend/README.md](./backend/README.md).
