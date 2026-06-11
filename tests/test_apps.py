"""Desktop-App-Liste: .desktop-Parsing und XDG-Suchpfade."""

from streamdeck_controller.apps import (
    list_desktop_apps, parse_desktop_file, strip_field_codes,
)


def write_desktop(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    if "Type=" not in body:
        body = body.replace("[Desktop Entry]\n", "[Desktop Entry]\nType=Application\n")
    path.write_text(body, encoding="utf-8")


def test_strip_field_codes():
    assert strip_field_codes("firefox %u") == "firefox"
    assert strip_field_codes("env FOO=1 app %F --flag") == "env FOO=1 app --flag"
    assert strip_field_codes("plain") == "plain"


def test_parse_desktop_file(tmp_path):
    f = tmp_path / "firefox.desktop"
    write_desktop(f, "[Desktop Entry]\nType=Application\nName=Firefox\nExec=firefox %u\n")
    assert parse_desktop_file(f) == ("Firefox", "firefox")


def test_parse_skips_hidden_and_nodisplay(tmp_path):
    hidden = tmp_path / "a.desktop"
    write_desktop(hidden, "[Desktop Entry]\nName=A\nExec=a\nNoDisplay=true\n")
    assert parse_desktop_file(hidden) is None

    terminal = tmp_path / "b.desktop"
    write_desktop(terminal, "[Desktop Entry]\nName=B\nExec=b\nTerminal=true\n")
    assert parse_desktop_file(terminal) is None

    no_type = tmp_path / "d.desktop"
    no_type.write_text("[Desktop Entry]\nName=D\nExec=d\n", encoding="utf-8")
    assert parse_desktop_file(no_type) is None  # Type ist Pflichtfeld


def test_parse_only_reads_desktop_entry_section(tmp_path):
    f = tmp_path / "c.desktop"
    write_desktop(f, "[Desktop Entry]\nName=C\nExec=c\n"
                     "[Desktop Action neu]\nName=Neues Fenster\nExec=c --new\n")
    assert parse_desktop_file(f) == ("C", "c")


def test_list_desktop_apps_prefers_user_dir(tmp_path, monkeypatch):
    user, system = tmp_path / "user", tmp_path / "system"
    monkeypatch.setenv("XDG_DATA_HOME", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(system))

    write_desktop(system / "applications" / "app.desktop",
                  "[Desktop Entry]\nName=System-Version\nExec=app\n")
    write_desktop(user / "applications" / "app.desktop",
                  "[Desktop Entry]\nName=Meine Version\nExec=app --custom\n")
    write_desktop(system / "applications" / "zzz.desktop",
                  "[Desktop Entry]\nName=Zett\nExec=zzz\n")

    apps = list_desktop_apps()
    assert apps == [("Meine Version", "app --custom"), ("Zett", "zzz")]
