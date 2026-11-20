# Bela Lab desktop

The desktop application uses the existing Python engine with pywebview and Windows WebView2. The frontend is local HTML/CSS/JavaScript with dedicated Play, Review and Library workspaces; it has no address bar, browser tabs, hosted service or paid API. Responsive mobile layouts share the same UI. This Windows build is not an Android or iOS package.

## Open the app

Use the **Bela Lab** desktop or Start menu shortcut, or `START_BELA.cmd` in the project root. The installed application contains Python and its required libraries. Windows WebView2 must be available (it is present on the development computer).

- Application: `%LOCALAPPDATA%/Programs/Bela Lab/Bela Lab.exe`
- Games and analysis: `%LOCALAPPDATA%/Bela Lab/saves/dashboard`
- Display preferences: `%LOCALAPPDATA%/Bela Lab/webview`
- Startup diagnostics: `%LOCALAPPDATA%/Bela Lab/desktop.log`

The initial installation copies active matches, private bot checkpoints, advice journals and review notes from the project. Subsequent installs preserve the app's existing data. The developer browser dashboard and the installed app have separate save folders after that first copy; they do not synchronize.

Closing the window cancels active analysis and shuts down its loopback server. Opening the app twice focuses the existing window. Nothing needs to be started in a terminal. The loopback port is 18766, separate from the developer dashboard on 8766. Downloads use the native WebView download flow. Saves are outside the installation so replacing the executable does not replace games.

## Build and install from this checkout

From PowerShell in the project root:

```powershell
python -m venv app/.venv
app/.venv/Scripts/python.exe -m pip install -r app/requirements-desktop.txt
app/.venv/Scripts/python.exe -m PyInstaller --noconfirm app/BelaLab.spec
powershell -ExecutionPolicy Bypass -File app/tools/install_desktop.ps1
```

The icon is tracked in `app/assets/bela-lab.ico`. The spec bundles the frontend, all card artwork, reference docs and examples. The build goes to ignored `dist/Bela Lab/`. Close an installed Bela Lab before updating. No administrator account is needed. This personal build is unsigned.

For source development, run `app/.venv/Scripts/python.exe app/desktop.py`. For the browser-based development dashboard, run `python app/run.py`. Existing text and simulation commands remain available through `app/run.py`.

## Frontend direction

Keep the Python engine independent of the interface. Continue extracting shared table, hand, navigation, analysis and modal styles into reusable frontend modules. The same HTML/CSS/JavaScript can be wrapped for a mobile client later; mobile distribution and engine execution need their own packaging work. Introducing a second UI framework now would duplicate the established gameplay and review interactions without improving the card engine.


## App workspaces

- **Play** keeps the hand and contract information on one felt table. The side inspector has Advice, Score and Events tabs. Trump advice opens automatically when a new calling phase starts.
- **Review** replays saved decisions with the existing analysis board and notes.
- **Library** holds saved matches and archive import.
- **Settings** contains labelled card style, language and appearance controls. Bot/manual mode is visible above the table. Existing preferences and game data are preserved.
- Deal and match results appear on the table with the relevant Next deal, Review and New match actions. Scores remain available in the inspector.
- Pause/Resume controls are in the command bar during bot play. Settings pauses automatic bot progression while it is open.
- Keyboard shortcuts: Ctrl+1 Play, Ctrl+2 Review, Ctrl+3 Library, Ctrl+, Settings.
- On narrow screens, navigation moves to the bottom and cards use two rows so their estimates remain readable.

These workspace changes affect the desktop shell. The browser dashboard remains available for development. Frontend assets are stored under the installed application's `_internal/bela/interfaces/web` directory; frontend-only updates do not require changing the engine or save files.


## Interface design system

The production interface uses warm paper light surfaces, plum dark surfaces, mulberry actions, and complementary teal/clay team colours. `desktop.css` owns application layout, typography, shared controls, interaction states and responsive rules; legacy viewport overrides were removed from `workspace.css`. The retained stylesheets supply card artwork and the underlying tracking components.

The spacing scale is 4, 8, 12, 16, 24 and 32px. Body and input text uses the system UI font at 13px; supporting data labels use 11–12px. Controls use 4px radii and structural panels 6px. Borders separate information; shadow is reserved for floating menus, dialogs and physical playing cards. Focus indicators use the action accent and reduced-motion preferences are respected.

Navigation keeps Play, Review and Library together, with the existing secondary tools below. Bot play/manual tracking switches are visible above the table. The score ledger separates match totals from the current deal; contract and caller details remain next to the table. The inspector is a single tabbed column. Settings are labelled rows. The Library uses a compact match table with Continue and Review actions, and becomes a compact list on phones. End-of-deal states show scores and next actions without decorative hero artwork.

Verification covers the calling/declaration/card-play path, preferences, direct Library-to-Review navigation, keyboard tabs, both themes and viewport widths from phone to desktop. These are frontend changes; scoring, legal moves, sampling, advice algorithms and saved-game formats remain unchanged.


The Bela Lab icon is a stylized Tref acorn inspired by the Hungarian deck. The canonical vector lives in `web/favicon.svg`; the matching Windows icon is `app/assets/bela-lab.ico`. Traditional playing-card colours are retained.


Suit naming is independent of artwork. Settings → Suit names offers standard names (Hearts, Spades, Diamonds, Clubs / Herc, Pik, Karo, Tref) or traditional Hungarian names. The standard names are the default, including when Hungarian artwork is selected. The choice is remembered and applies to setup, live play, advice and review.
