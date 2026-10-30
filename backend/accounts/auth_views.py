import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


def donnees_utilisateur(user):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "roles": list(user.groups.values_list("name", flat=True)),
    }




@require_GET
@ensure_csrf_cookie
def csrf_token(request):
    token = get_token(request)
    return JsonResponse({"csrfToken": token})



@require_POST
def connexion(request):
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Requête invalide."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"detail": "Requête invalide."}, status=400)

    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not username or not isinstance(password, str) or not password:
        return JsonResponse(
            {"detail": "Identifiant et mot de passe obligatoires."},
            status=400,
        )

    user = authenticate(
        request,
        username=username,
        password=password,
    )

    if user is None:
        return JsonResponse(
            {"detail": "Identifiant ou mot de passe incorrect."},
            status=401,
        )

    if not user.is_active:
        return JsonResponse(
            {"detail": "Ce compte est désactivé."},
            status=403,
        )

    login(request, user)

    return JsonResponse(donnees_utilisateur(user))


@require_GET
def session_utilisateur(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentification requise."}, status=401)

    return JsonResponse(donnees_utilisateur(request.user))


@require_POST
def deconnexion(request):
    logout(request)
    return JsonResponse({"detail": "Déconnexion réussie."})
