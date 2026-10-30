ROLE_MODULE_ACCESS = {
    "Administrateur": {
        "utilisateurs": "gestion",
        "stock": "gestion",
        "clients": "gestion",
        "fournisseurs": "gestion",
        "ventes": "gestion",
        "factures": "lecture",
        "rapports": "lecture",
        "caisse": "gestion",
    },
    "Responsable magasin": {
        "utilisateurs": "aucun",
        "stock": "lecture",
        "clients": "gestion",
        "fournisseurs": "gestion",
        "ventes": "gestion",
        "factures": "lecture",
        "rapports": "lecture",
        "caisse": "absent",
    },
    "Gestionnaire de stock": {
        "utilisateurs": "aucun",
        "stock": "gestion",
        "clients": "lecture",
        "fournisseurs": "gestion",
        "ventes": "lecture",
        "factures": "lecture",
        "rapports": "lecture",
        "caisse": "absent",
    },
    "Vendeur": {
        "utilisateurs": "aucun",
        "stock": "lecture",
        "clients": "gestion",
        "fournisseurs": "lecture",
        "ventes": "gestion",
        "factures": "lecture",
        "rapports": "lecture",
        "caisse": "absent",
    },
    "Caissier": {
        "utilisateurs": "aucun",
        "stock": "lecture",
        "clients": "gestion",
        "fournisseurs": "lecture",
        "ventes": "lecture",
        "factures": "lecture",
        "rapports": "lecture",
        "caisse": "gestion",
    },
}

ADMINISTRATOR_ROLE = "Administrateur"


def roles_with_write_access(module):
    return {
        role
        for role, modules in ROLE_MODULE_ACCESS.items()
        if modules.get(module) == "gestion"
    }
