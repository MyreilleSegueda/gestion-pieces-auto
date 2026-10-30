# Backend Django et API REST

## Installation locale

Depuis la racine du projet, crée un environnement virtuel et installe les dépendances :

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Configure les variables de `backend\.env.example` dans l'environnement avant de démarrer Django. Django ne charge pas automatiquement les fichiers `.env`. PostgreSQL reste le moteur configuré ; aucune base n'est créée ou remplacée automatiquement.

```powershell
backend\.venv\Scripts\python.exe backend\manage.py check
backend\.venv\Scripts\python.exe backend\manage.py test accounts inventory utilisateurs clients fournisseurs sales invoicing reports
backend\.venv\Scripts\python.exe backend\manage.py runserver
```

La découverte des tests sans argument annonce zéro test ; lance-les avec les noms d'applications. Les 57 tests passent sur la base PostgreSQL temporaire créée par Django pour les tests. La base métier n'est pas utilisée par cette suite.

## Migrations et sauvegardes

Les migrations `inventory/0003`, `inventory/0004`, `clients/0001`, `fournisseurs/0001`, `sales/0001` et `invoicing/0001` sont appliquées à la base locale de développement. Avant une autre migration, confirme la cible PostgreSQL, crée une sauvegarde et examine le plan :

```powershell
backend\.venv\Scripts\python.exe backend\manage.py showmigrations
pg_dump --format=custom --file=gestion_pieces_auto.dump --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER $env:POSTGRES_DB
backend\.venv\Scripts\python.exe backend\manage.py migrate --plan
```

Pour vérifier une restauration sans remplacer la base utilisée, restaure l'archive dans une base de test distincte :

```powershell
createdb --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER gestion_pieces_auto_restore_test
pg_restore --host=$env:POSTGRES_HOST --username=$env:POSTGRES_USER --dbname=gestion_pieces_auto_restore_test gestion_pieces_auto.dump
```

Les outils PostgreSQL demanderont le mot de passe si nécessaire. La sauvegarde et la restauration n'ont pas encore été exécutées dans cet environnement.

En production, définir `DJANGO_DEBUG=False`, fournir une nouvelle `DJANGO_SECRET_KEY`, des identifiants PostgreSQL via variables d'environnement et servir l'application derrière HTTPS.