from ai_video_studio.app import build_app


def test_build_app_sets_product_name(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = build_app([])
    assert app.applicationName() == "AI Video Translator & Dubbing Studio"
    app.quit()
