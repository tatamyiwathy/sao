# sao
Djangoの勤怠管理アプリです

## セットアップ

1. コードをzipでダウンロードやgit cloneなどでローカルに展開します

1. 展開したフォルダの中に```.env.example```ファイルがあるので、コピーで```.env```ファイルを作成します

        # cp .env.example .env
    

1. SECRET_KEYを生成して、`.env` の `SECRET_KEY` に設定します:
   ```sh
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   生成された値を `.env` の `SECRET_KEY=` の後ろに貼り付けてください。

1. DJANGO_SUPERUSER_PASSWORDとMYSQL_ROOT_PASSWORDは```PLEASE_SET_YOUR_OWN_PASSWORD```をユーザーが作成したパスワード文字列におきかえてください


1. SAO_PROFILEはアプリケーションのプロファイルを切り替えます。```dev```で開発バージョン、```prod```で製品バージョンに切り替わります

## 実行

```
docker compose up --build
```

## 使い方

ブラウザで ```http://localhost:8000/sao/```にアクセス

- 以下、作成中

## ライセンス

MIT

## 開発者

[tatamyiwathy](http://github.com/tatamyiwathy)