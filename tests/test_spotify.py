"""Spotify-Client (ohne Netzwerk)."""

from streamdeck_controller.spotify.client import SpotifyClient


def test_to_uri_from_link():
    assert SpotifyClient.to_uri(
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=x"
    ) == "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
    assert SpotifyClient.to_uri(
        "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy"
    ) == "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"


def test_to_uri_passthrough():
    assert SpotifyClient.to_uri("spotify:playlist:abc") == "spotify:playlist:abc"


def test_to_uri_invalid():
    assert SpotifyClient.to_uri("https://example.com/foo") is None
    assert SpotifyClient.to_uri("") is None


def test_not_ready_without_client_id(monkeypatch, tmp_path):
    from streamdeck_controller.spotify import auth
    monkeypatch.setattr(auth, "TOKEN_PATH", tmp_path / "token.json")
    client = SpotifyClient("")
    assert client.ready is False
