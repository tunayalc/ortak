#!/bin/zsh
# Adds the dSYMs of React Native's prebuilt iOS frameworks (React, ReactNativeDependencies,
# hermesvm) to an Xcode archive, so App Store uploads include them and crash reports for
# these frameworks can be symbolicated.
#
# Usage: scripts/add-prebuilt-dsyms.sh path/to/ORTAK.xcarchive
# Run after `xcodebuild archive` and before exporting or uploading.
# Versions come from ios/Podfile.lock; downloads are checked against Maven SHA-1 files and
# every dSYM must match the UUID of the binary inside the archive, otherwise nothing is added.
set -euo pipefail

ARCHIVE=${1:?xcarchive path required}
ROOT=${0:A:h:h}
LOCK=$ROOT/ios/Podfile.lock
MAVEN=https://repo1.maven.org/maven2/com/facebook
APP=$(find "$ARCHIVE/Products/Applications" -maxdepth 1 -name '*.app' | head -1)
[[ -d $APP ]] || { echo "Archive has no app: $ARCHIVE" >&2; exit 1; }

version() { sed -nE "s/^  - $1 \(([^)]+)\):?$/\1/p" "$LOCK" | head -1; }
RN=$(version React-Core-prebuilt)
HERMES=$(version hermes-engine)
[[ -n $RN && -n $HERMES ]] || { echo "Could not read versions from $LOCK" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

fetch() {  # url -> verified local file
  local url=$1 file=$WORK/${1:t}
  curl -sfLo "$file" "$url"
  [[ $(curl -sfL "$url.sha1" | cut -c1-40) == $(shasum -a 1 "$file" | cut -c1-40) ]] || { echo "SHA-1 mismatch: $url" >&2; exit 1; }
  echo "$file"
}

add() {  # framework tarball-url path-inside-tarball
  local name=$1 tarball dir binary dsym
  tarball=$(fetch "$2")
  dir=$WORK/$name; mkdir -p "$dir"
  tar -xzf "$tarball" -C "$dir"
  dsym=$dir/$3/$name.framework.dSYM
  binary=$APP/Frameworks/$name.framework/$name
  if [[ $(dwarfdump --uuid "$binary" | awk '{print $2}' | sort) != $(dwarfdump --uuid "$dsym" | awk '{print $2}' | sort) ]]; then
    echo "UUID mismatch for $name; not added." >&2; exit 1
  fi
  ditto "$dsym" "$ARCHIVE/dSYMs/$name.framework.dSYM"
  echo "Added $name.framework.dSYM"
}

add React "$MAVEN/react/react-native-artifacts/$RN/react-native-artifacts-$RN-reactnative-core-dSYM-release.tar.gz" ios-arm64
add ReactNativeDependencies "$MAVEN/react/react-native-artifacts/$RN/react-native-artifacts-$RN-reactnative-dependencies-dSYM-release.tar.gz" ios-arm64
add hermesvm "$MAVEN/hermes/hermes-ios/$HERMES/hermes-ios-$HERMES-hermes-framework-dSYM-release.tar.gz" iphoneos
