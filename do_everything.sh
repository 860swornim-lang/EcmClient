#!/usr/bin/env bash
# Put this next to ECMLauncher.zip, then:  bash do_everything.sh
# Unpacks the project, builds the Linux binary and copies it next to this file.
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -f ECMLauncher/builder.sh ]; then
    echo "Unpacking ECMLauncher.zip ..."
    (command -v unzip >/dev/null && unzip -oq ECMLauncher.zip) || python3 -m zipfile -e ECMLauncher.zip . \
        || { echo "Put ECMLauncher.zip next to this file."; exit 1; }
fi
bash ECMLauncher/builder.sh "$@" || exit 1
cp -f ECMLauncher/release/ECMLauncher ./ECMLauncher-linux && chmod +x ./ECMLauncher-linux
echo "All done - your launcher is: $(pwd)/ECMLauncher-linux"
