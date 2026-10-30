from django.db import models


class Client(models.Model):
    nom = models.CharField(max_length=200)
    telephone = models.CharField(max_length=30, blank=True)
    adresse = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "id"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.nom
