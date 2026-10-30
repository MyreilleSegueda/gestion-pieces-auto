# Frontend React

Application React servant d'interface au backend Django REST.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## Démarrage

Depuis la racine du projet, démarre Django puis Vite dans deux terminaux :

```powershell
backend\.venv\Scripts\python.exe backend\manage.py runserver
npm run dev --prefix frontend
```

Vite relaie `/api` vers Django sur `http://127.0.0.1:8000`. Ouvre l'URL affichée par Vite et garde le même hôte (`localhost` ou `127.0.0.1`) afin de conserver les cookies de session et CSRF.

## Contrôles

```powershell
npm run lint --prefix frontend
npm run build --prefix frontend
```


