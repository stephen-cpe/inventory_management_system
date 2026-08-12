# tests/conftest.py
# Shared pytest fixtures. The app fixture builds a fresh in-memory SQLite
# instance for every test, so tests are fully isolated and fast.
import pytest
from app import create_app
from extensions import db
from models import User


@pytest.fixture
def app():
    """A fresh application instance with an in-memory SQLite database."""
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A Werkzeug test client wired to the isolated app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A CLI runner for testing Flask CLI commands."""
    return app.test_cli_runner()


@pytest.fixture
def admin_user(app):
    """Create and return an admin user."""
    with app.app_context():
        user = User(username="admin", is_admin=True)
        user.set_password("adminpass")
        db.session.add(user)
        db.session.commit()
        # Detach so it can be referenced outside the session; return a fresh fetch
        return User.query.filter_by(username="admin").first()


@pytest.fixture
def regular_user(app):
    """Create and return a standard (non-admin) user."""
    with app.app_context():
        user = User(username="user1", is_admin=False)
        user.set_password("userpass")
        db.session.add(user)
        db.session.commit()
        return User.query.filter_by(username="user1").first()


@pytest.fixture
def logged_in_client(app, client, admin_user):
    """A test client already authenticated as the admin user."""
    response = client.post(
        "/login",
        data={"username": "admin", "password": "adminpass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return client


@pytest.fixture
def logged_in_regular_client(app, client, regular_user):
    """A test client authenticated as a standard (non-admin) user."""
    response = client.post(
        "/login",
        data={"username": "user1", "password": "userpass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return client