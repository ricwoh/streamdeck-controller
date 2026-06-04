from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_python_app_syntax():
    ast.parse((ROOT / "streamdeck_app.py").read_text())


def test_local_install_references_existing_app_file():
    install = (ROOT / "install.sh").read_text()
    wrapper = (ROOT / "streamdeck").read_text()
    assert "streamdeck_app.py" in install
    assert "streamdeck_app.py" in wrapper
    assert "streamdeck_controller.py" not in install
    assert "streamdeck_controller.py" not in wrapper


def test_pkgbuild_has_no_network_pip_install_in_build():
    pkgbuild = (ROOT / "aur" / "PKGBUILD").read_text()
    assert "pip install" not in pkgbuild
    assert "pyside6" in pkgbuild
    assert "python-pillow" in pkgbuild
    assert "python-elgato-streamdeck" in pkgbuild
    assert "python-pyside6" not in pkgbuild
    assert "python-streamdeck" not in pkgbuild
    assert "streamdeck-controller::git+https://github.com/ricwoh/streamdeck-controller.git" in pkgbuild


def test_desktop_files_have_stable_exec():
    for path in [ROOT / "appimage" / "streamdeck.desktop"]:
        text = path.read_text()
        assert "Exec=streamdeck-controller" in text
        assert "Type=Application" in text
        assert "Categories=Utility;HardwareSettings;" in text


def test_srcinfo_matches_pkgbuild_core_dependencies():
    srcinfo = (ROOT / "aur" / "aur-repo" / ".SRCINFO").read_text()
    for dep in ["python", "hidapi", "pyside6", "python-pillow", "python-elgato-streamdeck"]:
        assert f"depends = {dep}" in srcinfo
    assert "python-pyside6" not in srcinfo
    assert "python-streamdeck" not in srcinfo
    assert "source = streamdeck-controller::git+https://github.com/ricwoh/streamdeck-controller.git" in srcinfo
