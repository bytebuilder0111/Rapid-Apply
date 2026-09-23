from app.models import Role

PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "manage_clients",
        "manage_bidders",
        "manage_all_profiles",
    },
    Role.CLIENT: {
        "manage_own_profiles",
        "manage_own_integrations",
        "analyze",
        "view_own_analyses",
        "view_client_analyses",
    },
    Role.BIDDER: {
        "analyze",
        "view_own_analyses",
    },
}


def has_permission(role: Role, action: str) -> bool:
    return action in PERMISSIONS.get(role, set())
