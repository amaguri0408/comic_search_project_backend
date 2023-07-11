import csv
import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum

from app import app, db


class App(db.Model):
    __tablename__ = 'app'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    img_url = db.Column(db.String(255), nullable=False)
    platform_type = db.Column(Enum('app', 'web', name='platform_type_enum'), nullable=False)
    app_store_url = db.Column(db.String(255))
    google_play_url = db.Column(db.String(255))
    site_url = db.Column(db.String(255))

    def __repr__(self):
        return f'<App {self.id} {self.name}>' 
    
    @staticmethod
    def update():
        # テーブル全消し
        all_apps = App.query.all()
        for app_record in all_apps:
            db.session.delete(app_record)
        db.session.commit()

        with open(app.config['APP_CSV_PATH'], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                app_record = App(**row)
                db.session.add(app_record)
                print(f'add {app_record.name}')
            db.session.commit()


class Comic(db.Model):
    __tablename__ = 'comic'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    title_kana = db.Column(db.String(255), nullable=False)
    main_author = db.Column(db.String(255), nullable=False)
    sub_author = db.Column(db.String(255))
    app_id = db.Column(db.Integer, db.ForeignKey('app.id'), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    crawled_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<Comic {self.id} {self.title}>'
    

class CrawlHistory(db.Model):
    __tablename__ = 'crawl_history'
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey('app.id'), nullable=False)
    crawled_at = db.Column(db.DateTime, default=datetime.datetime.now(), nullable=False)
    status = db.Column(Enum('success', 'failure', name='crawl_status_enum'), nullable=False)
    comics_num = db.Column(db.Integer)
    detail = db.Column(db.String(255))

    def __repr__(self):
        return f'<CrawlHistory {self.app_id} {self.crawled_at}>'