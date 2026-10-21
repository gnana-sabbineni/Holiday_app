def test_pytest_works():
    assert 1 + 1 == 2

def test_app_imports():
    from app.main import app
    assert app is not None