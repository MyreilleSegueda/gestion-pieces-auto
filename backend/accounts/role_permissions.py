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


def is_administrator(user):
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name=ADMINISTRATOR_ROLE).exists()
        )
    )


def has_module_access(user, module, write=False):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    roles = user.groups.values_list("name", flat=True)
    required_access = {"gestion"} if write else {"lecture", "gestion"}
    return any(
        ROLE_MODULE_ACCESS.get(role, {}).get(module) in required_access
        for role in roles
    )


def roles_with_write_access(module):
    return {
        role
        for role, modules in ROLE_MODULE_ACCESS.items()
        if modules.get(module) == "gestion"
    }
