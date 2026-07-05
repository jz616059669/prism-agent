#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "$0")" && pwd)/.."

VERSION="2.1.2"
APP_NAME="PRISM-Agent"
BUILD_DIR="build-macos"
DIST_DIR="dist-macos"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"

echo "========================================"
echo "  PRISM Desktop macOS 打包"
echo "========================================"
echo ""

# 清理旧构建
if [ -d "${BUILD_DIR}" ]; then rm -rf "${BUILD_DIR}"; fi
if [ -d "${DIST_DIR}" ]; then rm -rf "${DIST_DIR}"; fi
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

echo "[1/4] 使用 flet build macos 构建..."
cd prism-desktop
flet build macos \
  --name "${APP_NAME}" \
  --output "${BUILD_DIR}" \
  --no-shared-libraries \
  prism_desktop/main.py

echo ""
echo "[2/4] 整理 .app bundle..."
APP_PATH="${BUILD_DIR}/${APP_NAME}.app"
if [ ! -d "${APP_PATH}" ]; then
  echo "[ERROR] .app bundle not found: ${APP_PATH}"
  exit 1
fi

# 设置版本和标识符
defaults write "${APP_PATH}/Contents/Info" CFBundleShortVersionString "${VERSION}"
defaults write "${APP_PATH}/Contents/Info" CFBundleVersion "${VERSION}"
defaults write "${APP_PATH}/Contents/Info" CFBundleIdentifier "com.prism.agent"
defaults write "${APP_PATH}/Contents/Info" CFBundleName "${APP_NAME}"
defaults write "${APP_PATH}/Contents/Info" CFBundleDisplayName "${APP_NAME}"
defaults write "${APP_PATH}/Contents/Info" LSMinimumSystemVersion "11.0"
defaults write "${APP_PATH}/Contents/Info" NSHighResolutionCapable true

# 移除 quarantine 属性（本地签名时可能需要）
xattr -cr "${APP_PATH}" 2>/dev/null || true

echo ""
echo "[3/4] 创建分发包..."
mkdir -p "${DIST_DIR}"
cp -R "${APP_PATH}" "${DIST_DIR}/"

echo ""
echo "[4/4] 完成"
echo "输出目录: ${DIST_DIR}"
ls -la "${DIST_DIR}/"

echo ""
echo "下一步："
echo "  1. 在 ${DIST_DIR} 中找到 ${APP_NAME}.app"
echo "  2. 双击运行测试"
echo "  3. 如需签名：codesign --force --deep --sign - ${APP_NAME}.app"
echo "  4. 如需打包 DMG：hdiutil create -volname ${APP_NAME} -srcfolder ${APP_NAME}.app ${APP_NAME}-${VERSION}.dmg"
