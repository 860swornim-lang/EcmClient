# ECM Launcher

ECM Launcher is a lightweight Python launcher for Minecraft Java Edition. It manages instances, Fabric and other loaders, Java runtimes, Modrinth downloads, offline profiles, and Microsoft browser sign-in.

## Run from source

```sh
python -m pip install -r requirements.txt
python main.py
```

On Linux, `./run.sh` creates a local virtual environment and starts the launcher. `./builder.sh` builds `release/ECMLauncher`; use `./builder.sh --install` to add it to the desktop menu. Building the ECM Fabric client jars requires JDK 25. The launcher downloads the Java runtime that each Minecraft version requests.

## Microsoft accounts

Microsoft sign-in opens the system browser and returns through a temporary localhost callback using PKCE. It does not collect your password or use a client secret. Microsoft requires a public-client application ID with Minecraft Java access; enter it in **Accounts**. Saved refresh tokens go into the operating system keyring, not the launcher JSON config. Offline profiles remain available.

## Skins and capes

Choose PNGs in **Skins & Capes**. Skins must be 64×64 or 64×32; capes must be 64×32. The launcher copies them into each selected instance before launch, where ECM Client applies them to your local player. These cosmetics are not uploaded and other players do not see them automatically.

## ECM Client builds

The custom Fabric client is built for Minecraft **1.21.11** and **26.2**. It provides the ECM title, loading, and pause screens; a right-Shift HUD editor with 31 toggleable HUD elements; accent colors; local skin/cape support; and MIT/ECMBro credits. Its launcher modules can also install compatible open-source Fabric mods such as Sodium, Lithium, FerriteCore, Iris, Xaero's Minimap, AppleSkin, Zoomify, and Mod Menu.

Build each mod from the repository root with:

```sh
./.project/build-linux.sh
./.project/26.2/build-linux.sh
```

The resulting jars are written to `client-mods/` and bundled into the Linux launcher. The Gradle wrappers download Gradle 9.8.0 on first use.

## Data folder

When run from source, game data is stored in `~/.ecmbro`. In a packaged build, it lives beside the launcher under `.ecmbro`. Override this with `ECM_HOME`.
