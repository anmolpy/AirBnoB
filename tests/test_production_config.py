import pytest
from flask import Flask
from app import _load_config, _assert_production_safe, create_app


def test_explicit_production_cannot_bypass_guard(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'development')
    app = Flask(__name__)
    _load_config(app, 'production')
    app.config['JWT_SECRET_KEY'] = 'CHANGE_ME_IN_PROD'
    with pytest.raises(RuntimeError):
        _assert_production_safe(app)


@pytest.mark.parametrize('secret', [None, '', 'short', 'CHANGE_ME_IN_PROD'])
def test_production_rejects_missing_or_weak_secret(secret):
    app = Flask(__name__)
    _load_config(app, 'production')
    app.config['JWT_SECRET_KEY'] = secret
    with pytest.raises(RuntimeError):
        _assert_production_safe(app)


def test_production_accepts_configured_secret_and_rejects_debug():
    app = Flask(__name__)
    _load_config(app, 'production')
    app.config['JWT_SECRET_KEY'] = 'synthetic-test-value-not-a-real-secret'
    _assert_production_safe(app)
    app.debug = True
    with pytest.raises(RuntimeError):
        _assert_production_safe(app)


def test_unknown_configuration_fails_closed():
    with pytest.raises(ValueError):
        create_app('prodution')
