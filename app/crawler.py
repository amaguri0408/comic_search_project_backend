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
    """例外処理を行うのとstatusを記録するデコレーター"""
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
            if self.comics:
                crawl_history = CrawlHistory(
                    app_id=self.app_record.id, 
                    comics_num=len(self.comics),
                    status='success'
                )
                res['status'] = 'success'
                res['comics_num'] = len(self.comics)
                status_code = 200
            else:
                crawl_history = CrawlHistory(
                    app_id=self.app_record.id, 
                    status='failure', 
                    detail='no comics'
                )
                res['status'] = 'failure'
                res['detail'] = 'no comics'
                status_code = 500
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
        elif self.app_record.name == 'サンデーうぇぶり':
            self.crawl_func = self._crawl_sunday_webry
        elif self.app_record.name == 'マガポケ':
            self.crawl_func = self._crawl_maga_poke
        elif self.app_record.name == 'マンガBANG！':
            self.crawl_func = self._crawl_manga_bang
        elif self.app_record.name == 'マンガUP！':
            self.crawl_func = self._crawl_manga_up
        elif self.app_record.name == '少年ジャンプ＋':
            self.crawl_func = self._crawl_shonen_jump_plus
        else:
            raise ValueError(f'app name is invalid {self.app_record.name}')
        self.comics = []
        # ルビ振り
        kakasi = pykakasi.kakasi()
        kakasi.setMode("J", "H")
        kakasi.setMode("K", "H")
        self.conv = kakasi.getConverter()

    def crawl(self):
        print(f'crawling {self.app_record.name}...')
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
    def _crawl_sunday_webry(self):
        """id:12 サンデーうぇぶりの作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, '/series')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        html = requests.get(load_url, headers=headers)
        soup = BeautifulSoup(html.content, "html.parser")
        datas_normal = soup.find_all("a", class_="webry-series-item-link")
        # 夜サンデー
        load_url = urljoin(self.app_record.site_url, '/series/yoru-sunday')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        html = requests.get(load_url, headers=headers)
        soup = BeautifulSoup(html.content, "html.parser")
        datas_yoru = soup.find_all("a", class_="webry-series-item-link")
        
        datas = datas_normal + datas_yoru
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("h4", class_="series-title").text
            title_kana = self.conv.do(title)
            author = data.find("p", class_="author").text
            author_list = author.split('/')
            main_author = ','.join(author_list[:min(2, len(author_list))])
            sub_author = ','.join(author_list[min(2, len(author_list)):])
            url = urljoin(self.app_record.site_url, data['href'])
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
    def _crawl_manga_bang(self):
        """id:19 マンガBANG!の作品一覧を取得"""
        i = 1
        while True:
            load_url = urljoin(self.app_record.site_url, f'/freemium/book_titles?page={i}')
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
            }
            html = requests.get(load_url, headers=headers)
            time.sleep(0.5)
            soup = BeautifulSoup(html.content, "html.parser")

            datas = soup.find("div", class_="js-react-on-rails-component")["data-props"]
            datas = eval(datas)["list"]["book_titles"]
            if not datas: break
            print(f'load {load_url}')
            crawled_at = datetime.datetime.now()
            for data in datas:
                self.comics.append({
                    'title': data["title"],
                    'title_kana': self.conv.do(data["title"]),
                    'main_author': data["author_name"],
                    'app_id': self.app_record.id,
                    'url': urljoin(self.app_record.site_url, f'freemium/book_titles{data["key"]}'),
                    'crawled_at': crawled_at,
                })
            i += 1


    @exception
    def _crawl_manga_up(self):
        """id:26 マンガUP！の作品一覧を取得"""
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
            url = urljoin(load_url + '/', data.find("a")['href'])
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
    def _crawl_shonen_jump_plus(self):
        """id:35 少年ジャンプ＋の作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, '/series')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        html = requests.get(load_url, headers=headers)
        soup = BeautifulSoup(html.content, "html.parser")
        datas_1 = soup.find_all("li", class_="series-list-item")

        load_url = urljoin(self.app_record.site_url, '/series/finished')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        html = requests.get(load_url, headers=headers)
        soup = BeautifulSoup(html.content, "html.parser")
        datas_2 = soup.find_all("li", class_="series-list-item")

        datas = datas_1 + datas_2
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("h2", class_="series-list-title").text
            title_kana = self.conv.do(title)
            author = data.find("h3", class_="series-list-author").text
            author_list = author.split('/')
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