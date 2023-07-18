import re
import time
import datetime
from urllib import request
from urllib.parse import urljoin

import requests
import pykakasi
from bs4 import BeautifulSoup

from app import db
from app.models import App, Comic, CrawlHistory


def exception(func):
    def wrapper(self, *args, **kwargs):
        res = {}
        try:
            func(self, *args, **kwargs)
        except Exception as e:
            crawl_history = CrawlHistory(
                app_id=self.app_record.id, 
                status='failure', 
                detail=str(e)
            )
            res['status'] = 'failure'
            res['detail'] = str(e)
            status_code = 500
        else:
            crawl_history = CrawlHistory(
                app_id=self.app_record.id, 
                comics_num=len(self.comics),
                status='success'
            )
            res['status'] = 'success'
            res['comics_num'] = len(self.comics)
            status_code = 200
        finally:
            db.session.add(crawl_history)
            db.session.commit()
        return {'dict': res, 'status_code': status_code}
    return wrapper


class ComicCrawler:
    def __init__(self, app_record: App):
        self.app_record = app_record
        if self.app_record.name == 'ガンガンONLINE':
            self.crawl_func = self._crawl_gangan_online
        elif self.app_record.name == 'マガポケ':
            self.crawl_func = self._crawl_maga_poke
        elif self.app_record.name == 'マンガUP！':
            self.crawl_func = self._crawl_manga_up
        else:
            raise ValueError(f'app name is invalid {self.app_record.name}')
        self.comics = []
        # ルビ振り
        kakasi = pykakasi.kakasi()
        kakasi.setMode("J", "H")
        kakasi.setMode("K", "H")
        self.conv = kakasi.getConverter()

    def crawl(self):
        return self.crawl_func()


    @exception
    def _crawl_gangan_online(self):
        """id:8, ガンガンONLINEの作品一覧を取得"""
        load_url = f"{self.app_record.site_url}/search"
        html = requests.get(load_url)
        soup = BeautifulSoup(html.content, "html.parser")

        # 作品一覧を取得
        datas = soup.find_all("a", class_=re.compile("SearchTitle_title"))
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("p", class_=re.compile("SearchTitle_title__name")).text
            if '読切' in title: continue

            # 著者
            author = data.find("p", class_=re.compile("SearchTitle_title__author")).text
            author_list = []
            for author_data in author.split('　'):
                if '／' in author_data:
                    author_list.append('／'.join(author_data.split('／')[1:]))
                else:
                    author_list.append(author_data)
            main_author = ','.join(author_list[:min(2, len(author_list))])
            sub_author = ','.join(author_list[min(2, len(author_list)):])
            
            url = f"{self.app_record.site_url}{data.get('href')}"
            title_kana = self.conv.do(title)
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'main_author': main_author,
                'sub_author': sub_author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })

    
    @exception
    def _crawl_maga_poke(self):
        """id:18, マガポケの作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, '/series')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        html = requests.get(load_url, headers=headers)
        soup = BeautifulSoup(html.content, "html.parser")

        datas = soup.find_all("li", class_="daily-series-item")
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("h4", class_="daily-series-title").text
            title_kana = self.conv.do(title)
            author = data.find("h5", class_="daily-series-author").text

            def func(x):
                if '/' in x: return x.split('/')[1]
                else: return x
            author_list = list(map(func, author.split(' ')))
            main_author = ','.join(author_list[:min(2, len(author_list))])
            sub_author = ','.join(author_list[min(2, len(author_list)):])

            url = data.find("a")["href"]
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'main_author': main_author,
                'sub_author': sub_author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


    @exception
    def _crawl_manga_up(self):
        load_url = urljoin(self.app_record.site_url, 'original')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        html = requests.get(load_url, headers=headers)
        soup = BeautifulSoup(html.content, "html.parser")

        datas = soup.find_all("li")
        crawled_at = datetime.datetime.now()
        for data in datas:
            if data.find("p", class_="ttl") is None: continue
            # print(data)
            title = data.find("p", class_="ttl").text
            title_kana = self.conv.do(title)
            author = data.find("p", class_="artist")
            # 任意のタブ<>で正規表現を使って区切る
            author_list = re.split(r'<.+?>', str(author))[1:-1]
            author_list = list(map(lambda x: re.split(r'[:：]', x)[-1], author_list))
            new_author_list = []
            for author_data in author_list:
                new_author_list.extend(author_data.split('・'))
            main_author = ','.join(new_author_list[:min(2, len(new_author_list))])
            sub_author = ','.join(new_author_list[min(2, len(new_author_list)):])
            url = urljoin(load_url, data.find("a")['href'])
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'main_author': main_author,
                'sub_author': sub_author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


    def save(self):
        # 同じアプリのcomicは削除
        delete_comic = Comic.query.filter_by(app_id=self.app_record.id)
        print(f'delete App {self.app_record.name} {delete_comic.count()} comics')
        delete_comic.delete()
        db.session.commit()

        for comic in self.comics:
            comic_record = Comic(**comic)
            db.session.add(comic_record)
        db.session.commit()
        print(f'add {len(self.comics)} comics')