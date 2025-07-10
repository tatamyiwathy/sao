# sao
Djangoの勤怠管理アプリです

## セットアップ

1. コードをzipでダウンロードやgit cloneなどでローカルに展開します

2. 展開したフォルダの中に```.env```ファイルを作成します

3. ```.env```ファイルを開いたら以下をコピペして、```PLEASE_SET_YOUR_OWN_PASSWORD```の部分をご自身のパスワードで置き換えてください

```
DJANGO_SUPERUSER_PASSWORD=PLEASE_SET_YOUR_OWN_PASSWORD
MYSQL_ROOT_PASSWORD=PLEASE_SET_YOUR_OWN_PASSWORD

# specify the profile for the SAO application
SAO_PROFILE=dev
# SAO_PROFILE=prod 
```
- DJANGO_SUPERUSER_PASSWORDはDjangoの管理者のパスワードです
- MYSQL_ROOT_PASSWORDはMySQLのrootユーザーのパスワードです
- SAO_PROFILEは```dev```で開発バージョン、```prod```で本番バージョンに切りかえます

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