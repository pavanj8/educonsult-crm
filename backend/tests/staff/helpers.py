"""Staff test helpers."""

from app.rbac.roles import Role


def make_staff_payload(
    *,
    email: str = "counselor@example.test",
    password: str = "secure-password",
    role: Role = Role.COUNSELOR,
    branch_id: int = 1,
) -> dict[str, str | int]:
    return {
        "email": email,
        "password": password,
        "role": role.value,
        "branch_id": branch_id,
    }
