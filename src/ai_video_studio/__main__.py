import sys

from ai_video_studio.app import build_app


def main() -> int:
    app = build_app(sys.argv)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
