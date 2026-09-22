from main import greet


def test_greet() -> None:
    assert greet("Mac") == "Hello, Mac!"
