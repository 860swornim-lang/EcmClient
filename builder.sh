#!/usr/bin/env bash
# ECM Launcher - Linux builder: produces ONE binary  release/ECMLauncher
#   ./builder.sh            build
#   ./builder.sh --install  build, then add ECM Launcher to your application menu
set -e
cd "$(dirname "$(readlink -f "$0")")"

echo "=========================================="
echo "  ECM Launcher - Linux single-binary builder"
echo "=========================================="

# ---- 1. Python 3.10+ ---------------------------------------------------------
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "[ERROR] Python 3.10 or newer is required (install python3 with your package manager)."
    exit 1
fi

# ---- 2. System packages: tkinter, venv, binutils (needed by PyInstaller) -----
SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="$(command -v sudo || true)"; fi
missing=0
"$PY" -c "import tkinter" 2>/dev/null       || missing=1
"$PY" -c "import venv, ensurepip" 2>/dev/null || missing=1
command -v objdump >/dev/null 2>&1          || missing=1

if [ "$missing" -eq 1 ]; then
    echo "[1/6] Installing system packages (tkinter, venv, binutils) ..."
    if   command -v apt-get >/dev/null; then   # Debian, Ubuntu, Mint, Pop!_OS, Kali, Zorin ...
        $SUDO apt-get update -y && $SUDO apt-get install -y python3-tk python3-venv python3-pip binutils
    elif command -v dnf >/dev/null; then       # Fedora, RHEL, Rocky, Alma, Nobara ...
        $SUDO dnf install -y python3-tkinter python3-pip binutils
    elif command -v yum >/dev/null; then
        $SUDO yum install -y python3-tkinter python3-pip binutils
    elif command -v pacman >/dev/null; then    # Arch, Manjaro, EndeavourOS, CachyOS ...
        $SUDO pacman -S --needed --noconfirm python tk python-pip binutils
    elif command -v zypper >/dev/null; then    # openSUSE
        $SUDO zypper --non-interactive install python3-tk python3-pip binutils
    elif command -v xbps-install >/dev/null; then   # Void
        $SUDO xbps-install -Sy python3-tkinter python3-pip binutils
    elif command -v apk >/dev/null; then       # Alpine (musl - see README)
        $SUDO apk add python3 py3-pip py3-tkinter binutils
    else
        echo "[ERROR] Unknown distro. Please install manually: python3 tkinter, python3 venv, binutils."
        exit 1
    fi
else
echo "[1/6] System packages found."
fi

# ---- 2. Virtual environment + requirements -----------------------------------
echo "[2/6] Preparing Python environment ..."
[ -x .venv/bin/python ] || "$PY" -m venv .venv
. .venv/bin/activate
python -m pip --version >/dev/null 2>&1 || python -m ensurepip --upgrade
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt pyinstaller

# ---- 3. Logos ------------------------------------------------------------------
if [ ! -f assets/logo/applogo/app_icon.png ]; then
echo "[3/6] Generating logos ..."
    python tools/make_logos.py
else
echo "[3/6] Logos found."
fi

# ---- 4. Build both Fabric client jars -----------------------------------------
echo "[4/6] Building ECM Client for Minecraft 1.21.11 and 26.2 ..."
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
./.project/build-linux.sh
./.project/26.2/build-linux.sh

# ---- 5. Build ------------------------------------------------------------------
echo "[5/6] Building ECMLauncher (about a minute) ..."
rm -rf build dist
pyinstaller --noconfirm --clean --onefile --windowed \
    --name ECMLauncher \
    --add-data "assets:assets" \
    --add-data "client-mods:client-mods" \
    --collect-all customtkinter \
    --collect-all minecraft_launcher_lib \
    --collect-all keyring \
    --collect-all secretstorage \
    --collect-all jeepney \
    --copy-metadata keyring \
    --copy-metadata SecretStorage \
    --hidden-import keyring.backends.SecretService \
    --hidden-import PIL._tkinter_finder \
    --hidden-import PIL._imagingtk \
    --hidden-import PIL.ImageTk \
    main.py

# ---- 6. Collect ----------------------------------------------------------------
echo "[6/6] Copying result ..."
mkdir -p release
cp -f dist/ECMLauncher release/ECMLauncher
chmod +x release/ECMLauncher
cp -f assets/logo/applogo/app_icon.png release/ECMLauncher.png
rm -rf build dist ECMLauncher.spec

# ---- optional: application-menu entry ---------------------------------------
if [ "$1" = "--install" ]; then
    DEST="$HOME/.local/share/ECMLauncher"
    mkdir -p "$DEST" "$HOME/.local/share/applications"
    cp -f release/ECMLauncher release/ECMLauncher.png "$DEST/"
    cat > "$HOME/.local/share/applications/ecmlauncher.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ECM Launcher
Comment=Offline Minecraft launcher
Exec="$DEST/ECMLauncher"
Path="$DEST"
Icon="$DEST/ECMLauncher.png"
Terminal=false
Categories=Game;
StartupWMClass=ECMLauncher
DESKTOP
    echo "Installed to $DEST (game data goes in $DEST/.ecmbro) and added to your menu."
fi

echo
echo "=========================================="
echo "  Done!  release/ECMLauncher"
echo "  Game data is stored in a .ecmbro folder next to the binary"
echo "=========================================="
