import pytest

from app.core.domain import BusinessRuleError, ConflictError
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.value_objects import CurrentUser, Email, Role


def _user(**overrides):
    data = dict(email=Email("Ana@Mederi.pe"), full_name=" Ana Pérez ", role=Role.MANAGER, password_hash="x", id=1)
    data.update(overrides)
    return User(**data)


def test_email_is_normalized_and_validated():
    assert Email(" Ana@Mederi.PE ").value == "ana@mederi.pe"
    with pytest.raises(BusinessRuleError):
        Email("no-es-correo")


def test_salesperson_needs_code():
    with pytest.raises(BusinessRuleError):
        _user(role=Role.SALESPERSON)
    assert _user(role=Role.SALESPERSON, salesperson_code="V01").salesperson_code == "V01"


def test_change_role_keeps_the_rule():
    user = _user()
    with pytest.raises(BusinessRuleError):
        user.change_role(Role.SALESPERSON, "  ")
    user.change_role(Role.SALESPERSON, "V02")
    assert user.to_current_user() == CurrentUser(1, Role.SALESPERSON, "V02")


def test_inactive_user_cannot_log_in():
    user = _user()
    user.deactivate(by=CurrentUser(2, Role.MANAGER, None))
    assert not user.can_log_in()


def test_cannot_deactivate_yourself():
    user = _user()
    with pytest.raises(ConflictError):
        user.deactivate(by=user.to_current_user())


def test_update_profile():
    user = _user()
    user.update_profile(Email("nuevo@mederi.pe"), "  ")
    assert user.email.value == "nuevo@mederi.pe"
    assert user.phone is None
    assert user.full_name == "Ana Pérez"
