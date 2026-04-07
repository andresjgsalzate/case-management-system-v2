import pytest


def test_current_user_dataclass_fields():
    from backend.src.core.middleware.permission_checker import CurrentUser
    user = CurrentUser(user_id="u1", email="a@b.com", role_id="r1", tenant_id="t1")
    assert user.user_id == "u1"
    assert user.scope == "own"  # default


def test_current_user_custom_scope():
    from backend.src.core.middleware.permission_checker import CurrentUser
    user = CurrentUser(user_id="u1", email="a@b.com", role_id="r1", tenant_id="t1", scope="all")
    assert user.scope == "all"


def test_permission_checker_instantiation():
    from backend.src.core.middleware.permission_checker import PermissionChecker
    checker = PermissionChecker(module="cases", action="read")
    assert checker.module == "cases"
    assert checker.action == "read"


def test_require_returns_depends():
    from fastapi import params
    from backend.src.core.middleware.permission_checker import require
    dep = require("cases", "read")
    assert isinstance(dep, params.Depends)
