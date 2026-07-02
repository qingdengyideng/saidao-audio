if __package__ in (None, ""):
    # Running the file directly (e.g. PyCharm "Run") has no package context,
    # so relative imports fail. Add the src root to sys.path and use an
    # absolute import instead.
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from saidao_audio.cli import main
else:
    from .cli import main


if __name__ == "__main__":
    main()
