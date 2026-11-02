from django.urls import path
from . import auth_views

urlpatterns = [
    path("csrf/", auth_views.csrf_token, name="csrf-token"),
    path("connexion/", auth_views.connexion, name="connexion"),
    path("session/", auth_views.session_utilisateur, name="session-utilisateur"),
    path("deconnexion/", auth_views.deconnexion, name="deconnexion"),
    path("mot-de-passe/", auth_views.changer_mot_de_passe, name="changer-mot-de-passe"),
]
