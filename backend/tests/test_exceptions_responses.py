import pytest
from backend.src.core.exceptions import (
    AppError, NotFoundError, ConflictError, ForbiddenError,
    ValidationError, UnauthorizedError,
)
from backend.src.core.responses import SuccessResponse, PaginatedResponse, ErrorResponse


class TestExceptions:
    def test_not_found_error(self):
        err = NotFoundError("Case", 42)
        assert err.code == "NOT_FOUND"
        assert "42" in err.message
        assert "Case" in err.message

    def test_conflict_error(self):
        err = ConflictError("Email already exists")
        assert err.code == "CONFLICT"

    def test_forbidden_error_default_message(self):
        err = ForbiddenError()
        assert err.code == "FORBIDDEN"
        assert err.message == "Access denied"

    def test_unauthorized_error(self):
        err = UnauthorizedError()
        assert err.code == "UNAUTHORIZED"

    def test_all_inherit_from_app_error(self):
        instances = [
            NotFoundError("Resource", 1),
            ConflictError("Duplicate entry"),
            ForbiddenError(),
            ValidationError("Invalid value"),
            UnauthorizedError(),
        ]
        for instance in instances:
            assert isinstance(instance, AppError)


class TestResponses:
    def test_success_response(self):
        response = SuccessResponse(data={"id": 1})
        assert response.success is True
        assert response.data == {"id": 1}
        assert response.message == "OK"

    def test_paginated_response_create(self):
        items = [1, 2, 3]
        response = PaginatedResponse.create(data=items, total=30, page=2, page_size=10)
        assert response.total == 30
        assert response.total_pages == 3
        assert response.page == 2
        assert response.success is True

    def test_paginated_response_partial_last_page(self):
        response = PaginatedResponse.create(data=[], total=25, page=3, page_size=10)
        assert response.total_pages == 3  # ceil(25/10) = 3

    def test_error_response(self):
        response = ErrorResponse(error="NotFound", code="NOT_FOUND", message="Item not found")
        assert response.success is False
        assert response.code == "NOT_FOUND"
