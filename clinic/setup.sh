#!/bin/bash
# PythonAnywhere 自動設定腳本
# 在 PythonAnywhere Bash console 輸入:
#   bash Claude-test/clinic/setup.sh

USERNAME=$(whoami)
CLINIC="/home/$USERNAME/Claude-test/clinic"
WSGI="/var/www/${USERNAME}_pythonanywhere_com_wsgi.py"

echo ""
echo "=== 物理治療所系統設定 ==="
echo ""

# 安裝 Flask
echo "▶ 安裝 Flask..."
pip install --user flask -q
echo "  完成"

# 寫入 WSGI 設定
if [ -f "$WSGI" ]; then
    cat > "$WSGI" <<EOF
import sys
sys.path.insert(0, '$CLINIC')
from wsgi import application
EOF
    echo "▶ WSGI 設定完成"
else
    echo "⚠  找不到 WSGI 檔案"
    echo "   請先到 Web 頁籤建立 Web App，再重新執行此腳本"
    exit 1
fi

echo ""
echo "=============================="
echo "✅ 設定完成！"
echo ""
echo "請到 Web 頁籤填入以下兩個路徑："
echo ""
echo "  Source code:      $CLINIC"
echo "  Working directory: $CLINIC"
echo ""
echo "填好後按 Reload 即可使用"
echo "=============================="
