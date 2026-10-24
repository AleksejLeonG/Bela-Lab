from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    # Relative imports/exports always resolve from the project, even when the
    # launcher is invoked from Explorer or from a different working directory.
    os.chdir(Path(__file__).resolve().parent.parent)
    arguments = sys.argv[1:]
    if arguments and arguments[0] in ("--text", "--tekst"):
        from bela.interfaces.player_cli import main
        main(arguments[1:])
    elif arguments and arguments[0] == "--batch":
        from bela.interfaces.batch_cli import main
        raise SystemExit(main(arguments[1:]))
    elif arguments and arguments[0] == "--practice-advice":
        from bela.interfaces.practice_advice import main
        main(arguments[1:])
    elif arguments and arguments[0] == "--trump":
        from bela.interfaces.trump_cli import main
        main(arguments[1:])
    elif arguments and arguments[0] == "--simulator":
        from bela.interfaces.simulator_cli import main
        sys.argv = [sys.argv[0], *arguments[1:]]
        main()
    else:
        from bela.interfaces.dashboard import main
        main(arguments)
