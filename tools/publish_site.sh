#!/bin/sh
# Publish site/ to the gh-pages branch (GitHub Pages: https://abdullahyahya1.github.io/wasla/).
set -eu
cd "$(dirname "$0")/.."
T=$(mktemp -d)
cp -R site/. "$T/"
touch "$T/.nojekyll"
git -C "$T" init -q
git -C "$T" checkout -q -b gh-pages
git -C "$T" add -A
git -C "$T" commit -qm "Website"
git -C "$T" push -q -f "$(git remote get-url origin)" gh-pages
echo "published"
