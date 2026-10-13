# NFSMW CrossSave v1.0

A Windows GUI utility for **Need for Speed: Most Wanted (2005)** save conversion between PC and GameCube, with an experimental GameCube regional-edition converter.

**This is a v1.0 feature release, not a claim that every regional conversion has been validated in-game.** Only the USA GameCube (`GOWE69`) and PC conversions have been tested in-game using supplied career saves. PAL/Japan conversions pass structural checks and require genuine regional saves and Dolphin gameplay tests.

## What's new in v1.0

- Removed the legacy **Repair old v0.2 GCI** button.
- Added a third mode: **GameCube → GameCube** for changing the target edition.
- Automatic source GameCube game ID detection when browsing or inspecting saves.
- GameCube edition selector for **PC → GameCube** and **GameCube → GameCube**.
- Preserves the **GameCube-native career payload byte-for-byte** during a region-only change, unless you explicitly edit the profile name or cash.
- Rebuilds GCI directory identity, banner/comment prelude and media checksum for the chosen target game ID.
- GameCube output names include the destination game ID, e.g. `SAVE-GOWP69-converted.gci`.
- Checks for conflicting GameCube identities in the destination folder using **both game ID and internal filename**, rather than Windows filenames.
- Preserves the established blue-and-white GUI, donor-free conversion, cash override, automatic backups, and Windows EXE build script.

## Recognized GameCube editions

| Edition | Game ID | Status |
|---|---|---|
| USA / English | `GOWE69` | **In-game tested** with PC ↔ GC career saves |
| PAL / English | `GOWP69` | **Experimental** |
| PAL / German | `GOWD69` | **Experimental** |
| PAL / French | `GOWF69` | **Experimental** |
| Japan / Japanese | `GOWJ13` | **Experimental** |

Only these five editions are selectable. Other possible IDs, including `GOWJ69`, are deliberately rejected pending confirmation of the correct save layout. Recognizing a retail game ID does **not** establish save-format compatibility.

## Download

**[Download the Windows EXE from GitHub Releases](https://github.com/ChatProductions/NFSMW-CrossSave/releases/latest)** once the Windows build succeeds.

No Python installation is required for the standalone executable. For source use or local builds, see the instructions below. The [Actions build page](https://github.com/ChatProductions/NFSMW-CrossSave/actions) also provides downloadable Windows build artifacts after successful runs.

If no release is visible yet, open **Actions → Build and release Windows EXE → Run workflow → Run workflow**. The successful run creates the first v1.0.0 release and also provides a downloadable EXE artifact. If GitHub asks you to enable workflows for this new repository, enable them first.

### Screenshots

![GameCube to PC](docs/GUI_GameCube_to_PC.png)

![PC to GameCube](docs/GUI_PC_to_GameCube.png)

![GameCube to GameCube region converter](docs/GUI_GameCube_to_GameCube.png)

## Running on Windows

1. Extract the ZIP to a folder.
2. Install **Python 3.10 or newer** if it is not installed.
3. Double-click **`Start Converter.bat`** to open the GUI.
4. Choose a conversion mode, select the input save, and optionally choose an output folder.
5. For GameCube output, select the destination edition and optionally enter an internal profile name.
6. Click **Inspect save** and then **Convert and verify**.
7. Back up your Dolphin memory card before importing the result. Test a regional conversion on a copy of the card first.

### The three modes

**GameCube → PC:** Select an exported `.gci` file. The program detects its game ID and creates `PROFILE\PROFILE` for `Documents\NFS Most Wanted\`. Source GameCube editions other than USA are untested in-game.

**PC → GameCube:** Select the extensionless PC profile file (e.g. `Documents\NFS Most Wanted\SAVE\SAVE`), choose the target GameCube edition. By default, the internal profile is suffixed with `GC` (example `SAVE → SAVEGC`) to avoid collisions. You can supply a different name.

**GameCube → GameCube:** Select the source `.gci`, then choose the target edition. The internal profile name is **preserved by default** across regions. To create another save for the *same* edition, supply a different internal profile name. A region-only conversion leaves the embedded MC02 career block unchanged; it changes the surrounding GCI metadata, not the in-game language.

### EXE build

On Windows, double-click **`Build Windows EXE.bat`** (or run `Build Windows EXE.ps1`). The script installs PyInstaller and builds:

`dist\NFSMW-CrossSave-v1.0.exe`

The EXE is a portable standalone Windows application and does not require Python on the destination computer. **The ZIP contains source code and build scripts, not a precompiled EXE.**

You can also copy `.github-workflow-example.yml` to `.github/workflows/build-windows.yml` in your GitHub repository and run its Windows workflow to obtain an EXE artifact.

## Validation and limitations

- PC ↔ USA GameCube: confirmed by user in both games on specific career saves; other saves may vary.
- Five GameCube game IDs: wrapper structure and checksums tested offline; **no PAL or Japanese in-game validation**.
- GameCube → GameCube: verified that a region-only transfer preserves the complete embedded career block and that the new GCI passes structural checks. Whether each regional game loads it remains unknown.
- Japanese-language profile names with non-ASCII characters are **not supported**. The program will reject unsupported name encodings instead of silently corrupting them.
- Expects an exported `.gci`, not a raw `.raw` memory card image, `.sav`, PS2 or Xbox save.
- The built-in GameCube banner/icon is a generic replacement. Regional banner and localization-specific metadata may differ from original regional saves.
- Source files are never edited. If the selected output path already exists, the app requests confirmation and writes a timestamped backup before replacing it.
- The app verifies checksums, names, and wrapper structure; it cannot verify that a particular game's career menu or garage will load without an in-game test.

## Testing

`python self_test.py` runs the scaffold sanity checks. For fixture-based tests:

`python self_test.py original_USA.gci known_good_PC broken_v02.gci`

`python test_regions.py original_USA.gci known_good_PC`

The regional suite checks all five game IDs, GC → GC → GC round-trips, PC → GC → PC conversion, preservation of native career data, and rejection of unsupported IDs/corrupt saves. **No personal saves are bundled.**

## References

- [Dolphin Emulator Wiki: Need for Speed: Most Wanted](https://wiki.dolphin-emu.org/forum/Need%20for%20Speed%3A%20Most%20Wanted/embed)
- [GameTDB GameCube edition IDs](https://www.gametdb.com/Wii/List?p=29&q=)
- [dbalatoni13/nfsmw](https://github.com/dbalatoni13/nfsmw) (reverse-engineered save structures)
- [sprintstate/nfs-mw-save-editor](https://github.com/sprintstate/nfs-mw-save-editor)

Independent fan-made research utility. Not affiliated with or endorsed by Electronic Arts or Nintendo.