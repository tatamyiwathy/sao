#!/bin/bash

# 変換対象のディレクトリ（カレントディレクトリなら .）
TARGET_DIR="."

echo "改行コード変換開始：CRLF → LF"

# 対象ファイルをすべて取得して変換
find "$TARGET_DIR" -type f | while read -r file; do
  echo "処理中: $file"
  nkf -Lu --overwrite "$file"
done

echo "完了しました！"