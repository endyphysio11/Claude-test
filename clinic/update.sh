#!/bin/bash
# 更新腳本：在 PythonAnywhere Bash 執行此腳本來套用最新版本
# 使用方式：bash Claude-test-main/clinic/update.sh

USERNAME=$(whoami)
PROJECT=$(find /home/$USERNAME -maxdepth 1 -type d -name "Claude-test*" | head -1)

if [ -z "$PROJECT" ]; then
  echo "❌ 找不到專案資料夾，請確認已上傳專案"
  exit 1
fi

echo "▶ 更新中... ($PROJECT)"
git -C "$PROJECT" pull origin main 2>/dev/null || echo "  （非 git 安裝，略過 pull）"

echo "✅ 更新完成"
echo ""
echo "請到 Web 頁籤按 Reload 讓變更生效"
