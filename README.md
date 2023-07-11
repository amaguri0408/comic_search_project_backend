# comic_search

## データベース更新

データベースを変更したいときは，`Models.py`に変更を記述して以下のコマンドを実行する．

```bash
flask db migrate
flask db upgrade
```

## Appデータ

アプリのデータは`app_info.csv`とAppテーブルで管理している．
内容を更新したいときは`app_info.csv`を編集して，それをAppテーブルに同期させる．
以下のコマンドで同期させることができる．

まず，shellを起動する
```bash
flask shell
```
その後以下を実行．
```python
App.update()
```

