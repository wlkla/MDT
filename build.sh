#!/bin/bash
rm -rf dist build
pyrcc5 -o res_rc.py res.qrc
pyinstaller MDT.spec
echo "打包完成，生成路径: dist/MDT.app"
