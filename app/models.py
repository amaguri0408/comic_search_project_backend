import os
import csv
import time
import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum

from app import app, db


class App(db.Model):
    __tablename__ = 'app'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    abj_management_number = db.Column(db.String(255))
    company_name = db.Column(db.String(255))
    service_type = db.Column(Enum('基本無料', '最新話無料', name='service_type_enum'))
    img_url = db.Column(db.String(255), nullable=False)
    platform_type = db.Column(db.String(20))
    app_store_url = db.Column(db.String(500))
    google_play_url = db.Column(db.String(500))
    site_url = db.Column(db.String(500))
    crawl_status = db.Column(db.String(30))
    crawl_histories = db.relationship('CrawlHistory', backref='crawl', lazy='dynamic')

    def __repr__(self):
        return f'<App {self.id} {self.name}>' 
    
    @staticmethod
    def update_image_url(app_record):
        res_record = app_record
        if app_record.img_url:
            return res_record

        if os.path.exists(f'app/static/images/app/{app_record.id}.png'):
            res_record.img_url = f'/static/images/app/{app_record.id}.png'
            return res_record

        try:
            if app_record.platform_type in ('app', 'both'):
                load_url = app_record.app_store_url
                driver = webdriver.Chrome()
                driver.get(load_url)

                # class="we-artwork__image"のimgタグのsrcを取得
                img_tag = driver.find_element(By.CSS_SELECTOR, ".we-artwork__image")
                img_url = img_tag.get_attribute('currentSrc')
                driver.quit()
                time.sleep(1)
                # ダウンロードして保存
                img = requests.get(img_url)
                file_name = f'app/static/images/app/{app_record.id}.png'
                with open(file_name, 'wb') as f:
                    f.write(img.content)
                res_record.img_url = file_name[file_name.find('/'):]
                return res_record
            
            if 'web' in app_record.platform_type:
                load_url = app_record.site_url
                html = requests.get(load_url)
                soup = BeautifulSoup(html.content, "html.parser")

                # rel='icon'のlinkタグのhrefを取得
                link_tag = soup.find(rel="icon")
                img_url = link_tag.get('href')
                if img_url.startswith('//'):
                    img_url = f'https:{img_url}'
                elif 'http' != img_url[:4]:
                    img_url = urljoin(load_url, img_url)
                # ダウンロードして保存
                img = requests.get(img_url)
                file_name = f'app/static/images/app/{app_record.id}.png'
                with open(file_name, 'wb') as f:
                    f.write(img.content)
                res_record.img_url = file_name[file_name.find('/'):]
                return res_record
            
            print(f'platform_type is invalid {app_record.platform_type}')
            return res_record
            
        except Exception as e:
            print('failed to get image_url')
            print(e)
            return res_record

    @staticmethod
    def update():
        with open(app.config['APP_CSV_PATH'], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if App.query.filter_by(id=row['id']).first():
                    app_record = App.query.filter_by(id=row['id']).first()
                    print(f'update {app_record.name}')
                    app_record.name = row['name']
                    app_record.img_url = row['img_url']
                    app_record.platform_type = row['platform_type']
                    app_record.app_store_url = row['app_store_url']
                    app_record.google_play_url = row['google_play_url']
                    app_record.site_url = row['site_url']
                    app_record.abj_management_number = row['abj_management_number']
                    app_record.company_name = row['company_name']
                    app_record.service_type = row['service_type']
                    app_record.crawl_status = row['crawl_status']
                    app_record = App.update_image_url(app_record)
                else:
                    app_record = App(**row)
                    print(f'add {app_record.name}')
                    app_record = App.update_image_url(app_record)
                    db.session.add(app_record)
                print(app_record.platform_type)
                db.session.commit()
                print(f'done')


class Comic(db.Model):
    __tablename__ = 'comic'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    title_kana = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    raw_author = db.Column(db.String(255))
    crawls = db.relationship('Crawl', backref='comic', lazy='joined')

    def __repr__(self):
        return f'<Comic {self.id} {self.title}>'
    
    @staticmethod
    def add_comic(comic_data):
        comic_query = Comic.query.filter(Comic.title == comic_data.title)
        assert comic_query.count() <= 1, f'comic_query must be 1, but {comic_query}'
        comic_query = comic_query.first()
        if comic_query:
            if not comic_query.author and comic_data.author:
                comic_query.author = comic_data.author
                db.session.commit()
            return comic_query.id
        else:
            db.session.add(comic_data)
            db.session.commit()
            return comic_data.id


class Crawl(db.Model):
    __tablename__ = 'crawl'
    id = db.Column(db.Integer, primary_key=True)
    comic_id = db.Column(db.Integer, db.ForeignKey('comic.id'), nullable=False)
    app_id = db.Column(db.Integer, db.ForeignKey('app.id'), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    crawled_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<Crawl {self.id} {self.url}>'
    
    
    @staticmethod
    def add_crawl(crawl_data):
        new_comic = Comic(
            title=crawl_data['title'].strip(), 
            title_kana=crawl_data['title_kana'].strip(), 
            author=crawl_data['author'],
            raw_author=crawl_data['raw_author'].strip(),
        )
        comic_id = Comic.add_comic(new_comic)
        crawl = Crawl(
            comic_id=comic_id,
            app_id=crawl_data['app_id'],
            url=crawl_data['url'],
            crawled_at=crawl_data['crawled_at'],
        )
        db.session.add(crawl)
        db.session.commit()


class CrawlHistory(db.Model):
    __tablename__ = 'crawl_history'
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey('app.id'), nullable=False)
    crawled_at = db.Column(db.DateTime, default=datetime.datetime.now(), nullable=False)
    status = db.Column(Enum('success', 'failure', name='crawl_status_enum'), nullable=False)
    comics_num = db.Column(db.Integer)
    detail = db.Column(db.String(1000))

    def __repr__(self):
        return f'<CrawlHistory {self.app_id} {self.crawled_at}>'