#!/bin/bash

# MDT 应用打包脚本

echo "清理旧的构建文件..."
rm -rf dist build

echo "编译资源文件..."
pyrcc5 -o res_rc.py res.qrc

echo "使用 PyInstaller 打包..."
pyinstaller MDT.spec --clean

if [ $? -ne 0 ]; then
    echo "打包失败！"
    exit 1
fi

echo "打包完成！"

# 查找应用路径
APP_PATH="dist/MDT.app"

if [ ! -d "$APP_PATH" ]; then
    echo "未找到应用包：$APP_PATH"
    exit 1
fi

# 使用临时签名（Ad-hoc signing）
echo "为应用签名..."
codesign --force --deep --sign - --entitlements entitlements.plist --options runtime "$APP_PATH"

if [ $? -eq 0 ]; then
    echo "签名完成！"
    # 验证签名
    echo ""
    echo "验证签名信息："
    codesign -dv --verbose=4 "$APP_PATH" 2>&1 | head -n 10
else
    echo "签名失败，但应用可能仍然可用"
fi

echo ""
echo "================================================"
echo "构建完成！应用位于：$APP_PATH"
echo "================================================"
echo ""
echo "重要提示："
echo "1. 首次运行时，需要在「系统设置」→「隐私与安全性」→「辅助功能」中添加 MDT"
echo "2. 如果遇到权限问题，请确保已授予必要的权限"
echo "3. 如需分发应用，建议使用开发者证书进行签名"
