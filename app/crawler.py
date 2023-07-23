import re
import time
import datetime
from tqdm import tqdm
from urllib import request
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse

import requests
import pykakasi
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from app import db
from app.models import App, Comic, Crawl, CrawlHistory


class RobotsTxtError(Exception):
    """RobotsTxtのエラー"""
    pass


class RobotsTxt:
    def __init__(self, url):
        self.url = url
        self._get_robots_txt()
        self._parse_robots_txt()

    def _get_robots_txt(self):
        """robots.txtを取得する"""
        res = requests.get(
            urljoin(self.url, 'robots.txt')
        )
        if res.status_code != 200:
            self.robots_txt = ""
            return
        self.robots_txt = res.text            
        # コメントを除去する
        self.robots_txt = re.sub(r'#.*\n', '', self.robots_txt)

    def _parse_robots_txt(self):
        """robots.txtを解析する"""
        self.robots_dict = {
            'crawl-delay': 1,
            'disallow': [],
            'allow': [],
            'sitemap': [],
            'else': []
        }        
        if not self.robots_txt: return

        agents = self.robots_txt.split('\n\n')
        my_agent = list(filter(lambda x: x.startswith('User-agent: *'), agents))
        if not my_agent: return 
        my_agent = my_agent[0]
        for line in my_agent.split('\n')[1:]:
            line = line.split(': ')
            if len(line) != 2: continue
            if line[0] == 'Crawl-delay':
                self.robots_dict[line[0].lower()] = int(line[1])
            elif line[0] in ['Disallow', 'Allow', 'Sitemap']:
                self.robots_dict[line[0].lower()].append(line[1])
            else:
                self.robots_dict['else'].append(line)
    
    def apply_crawl_delay(self):
        """クロール間隔を取得する"""
        time.sleep(self.robots_dict['crawl-delay'])
    
    def check_disallow(self, url):
        """urlがdisallowされているかを判定する"""
        url_path = urlparse(url).path
        if url_path == '': url_path = '/'
        if url_path in self.robots_dict['disallow']:
            raise RobotsTxtError(f'{url} is disallowed by robots.txt')


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
        if self.app_record.name == 'COMIC FUZ':
            self.crawl_func = self._crawl_comic_fuz
        elif self.app_record.name == 'LINEマンガ':
            self.crawl_func = self._crawl_line_manga
        elif self.app_record.name == 'ガンガンONLINE':
            self.crawl_func = self._crawl_gangan_online
        elif self.app_record.name == 'コミックDAYS':
            self.crawl_func = self._crawl_comic_days
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
        elif self.app_record.name in ('裏サンデー', 'マンガワン'):
            self.crawl_func = self._crawl_ura_sunday
        else:
            raise ValueError(f'app name is invalid {self.app_record.name}')
        if self.app_record.site_url:
            self.robots_txt = RobotsTxt(self.app_record.site_url)
        self.comics = []
        # ルビ振り
        kakasi = pykakasi.kakasi()
        kakasi.setMode("J", "H")
        kakasi.setMode("K", "H")
        self.conv = kakasi.getConverter()


    def get_soup(self, url):
        """urlからsoupを取得する"""
        self.robots_txt.check_disallow(url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.content, 'html.parser')
        self.robots_txt.apply_crawl_delay()
        return soup


    def crawl(self):
        print(f'crawling {self.app_record.name}...')
        return self.crawl_func()
    

    @exception
    def _crawl_comic_fuz(self):
        """id:2 COMIC FUZの作品一覧を取得"""
        crawled_at = datetime.datetime.now()
        load_url = f"{self.app_record.site_url}/rensai"
        self.robots_txt.check_disallow(load_url)
        driver = webdriver.Chrome(ChromeDriverManager().install())
        driver.get(load_url)
        self.robots_txt.apply_crawl_delay()

        # 作品一覧を取得
        a_tags = driver.find_elements(By.CSS_SELECTOR, ".Title_title__mh5OI")
        href_list = [a_tag.get_attribute('href') for a_tag in a_tags]

        # 作品詳細ページに遷移
        for href in tqdm(href_list):
            self.robots_txt.check_disallow(href)
            driver.get(href)
            self.robots_txt.apply_crawl_delay()
            # class="title_detail_introduction__name__Qr8HU"のタイトルを取得
            title = driver.find_element(By.CSS_SELECTOR, ".title_detail_introduction__name__Qr8HU").text
            author_list = list(map(lambda x: x.text, driver.find_elements(By.CSS_SELECTOR, ".AuthorTag_author__name__IthhZ")))
            self.comics.append({
                'title': title,
                'title_kana': self.conv.do(title),
                'author': ','.join(author_list),
                'raw_author': ' '.join(author_list),
                'app_id': self.app_record.id,
                'url': href,
                'crawled_at': crawled_at,
            })
        driver.quit()


    @exception
    def _crawl_line_manga(self):
        """id:4 LINEマンガの作品一覧を取得"""
        crawled_at = datetime.datetime.now()
        load_url = urljoin(self.app_record.site_url, '/periodic/gender_ranking?gender=0')
        self.robots_txt.check_disallow(load_url)
        driver = webdriver.Chrome(ChromeDriverManager().install())
        driver.get(load_url)
        self.robots_txt.apply_crawl_delay()

        pre_comic_len = 0
        # 止まるまでスクロール
        stop_flag = False
        while not stop_flag:
            # スクロールの高さを取得
            scroll_height = driver.execute_script("return document.body.scrollHeight")
            # スクロール
            driver.execute_script(f"window.scrollTo(0, {scroll_height});")
            self.robots_txt.apply_crawl_delay()

            rank_div = driver.find_element(By.CSS_SELECTOR, ".MdCMN05List")
            comic_list = rank_div.find_elements(By.CSS_SELECTOR, "a")
            print(len(comic_list))

            i = 0
            while len(comic_list) == pre_comic_len:
                self.robots_txt.apply_crawl_delay()
                rank_div = driver.find_element(By.CSS_SELECTOR, ".MdCMN05List")
                comic_list = rank_div.find_elements(By.CSS_SELECTOR, "a")
                print(f"stop: {i}, {len(comic_list)}")
                if i >= 10:
                    stop_flag = True
                    break
                i += 1
            
            pre_comic_len = len(comic_list)


        href_list = [a_tag.get_attribute('href') for a_tag in comic_list]
        for href in tqdm(href_list):
            self.robots_txt.check_disallow(href)
            driver.get(href)
            self.robots_txt.apply_crawl_delay()
            title = driver.find_element(By.CSS_SELECTOR, ".mdMNG01Ttl").text
            author_list = driver.find_element(By.CSS_SELECTOR, ".mdMNG04Dd02").find_elements(By.CSS_SELECTOR, "a")
            author_list = list(map(lambda x: x.text.strip(), author_list))
            self.comics.append({
                'title': title,
                'title_kana': self.conv.do(title),
                'author': '',
                'raw_author': ' '.join(author_list),
                'app_id': self.app_record.id,
                'url': href,
                'crawled_at': crawled_at,
            })
        driver.quit()


    @exception
    def _crawl_gangan_online(self):
        """id:8, ガンガンONLINEの作品一覧を取得"""
        load_url = f"{self.app_record.site_url}/search"
        soup = self.get_soup(load_url)

        # 作品一覧を取得
        datas = soup.find_all("a", class_=re.compile("SearchTitle_title"))
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("p", class_=re.compile("SearchTitle_title__name")).text
            if '読切' in title: continue

            # 著者
            raw_author = data.find("p", class_=re.compile("SearchTitle_title__author")).text
            author_list = []
            for author_data in raw_author.split('　'):
                if '／' in author_data:
                    author_list.append('／'.join(author_data.split('／')[1:]))
                else:
                    author_list.append(author_data)
            
            url = f"{self.app_record.site_url}{data.get('href')}"
            title_kana = self.conv.do(title)
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'author': ','.join(author_list),
                'raw_author': raw_author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


    @exception
    def _crawl_comic_days(self):
        """id:9 コミックDAYSの作品一覧を取得"""
        crawled_at = datetime.datetime.now()
        load_url = urljoin(self.app_record.site_url, '/series')
        soup = self.get_soup(load_url)
        datas = soup.find_all("li", class_="daily-series-item")
        for data in datas:
            title = data.find("h4", class_="daily-series-title").text
            author = data.find("h5", class_="daily-series-author").text
            author_list = author.split("/")
            a_tag = data.find("a")
            if not a_tag: continue
            url = a_tag["href"]
            self.comics.append({
                'title': title,
                'title_kana': self.conv.do(title),
                'author': ','.join(author_list),
                'raw_author': author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


    @exception
    def _crawl_sunday_webry(self):
        """id:12 サンデーうぇぶりの作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, '/series')
        soup = self.get_soup(load_url)
        datas_normal = soup.find_all("a", class_="webry-series-item-link")
        # 夜サンデー
        load_url = urljoin(self.app_record.site_url, '/series/yoru-sunday')
        soup = self.get_soup(load_url)
        datas_yoru = soup.find_all("a", class_="webry-series-item-link")
        
        datas = datas_normal + datas_yoru
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("h4", class_="series-title").text
            title_kana = self.conv.do(title)
            author = data.find("p", class_="author").text
            author_list = author.split('/')
            url = urljoin(self.app_record.site_url, data['href'])
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'author': ','.join(author_list),
                'raw_author': author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })

    
    @exception
    def _crawl_maga_poke(self):
        """id:18, マガポケの作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, '/series')
        soup = self.get_soup(load_url)

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

            url = data.find("a")["href"]
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'author': ','.join(author_list),
                'raw_author': author,
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
            soup = self.get_soup(load_url)

            datas = soup.find("div", class_="js-react-on-rails-component")["data-props"]
            datas = eval(datas)["list"]["book_titles"]
            if not datas: break
            print(f'load {load_url}')
            crawled_at = datetime.datetime.now()
            for data in datas:
                self.comics.append({
                    'title': data["title"],
                    'title_kana': self.conv.do(data["title"]),
                    'author': '',
                    'raw_author': data["author_name"],
                    'app_id': self.app_record.id,
                    'url': urljoin(self.app_record.site_url, f'freemium/book_titles{data["key"]}'),
                    'crawled_at': crawled_at,
                })
            i += 1


    @exception
    def _crawl_manga_up(self):
        """id:26 マンガUP！の作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, 'original')
        soup = self.get_soup(load_url)

        datas = soup.find_all("li")
        crawled_at = datetime.datetime.now()
        for data in datas:
            if data.find("p", class_="ttl") is None: continue
            # print(data)
            title = data.find("p", class_="ttl").text
            title_kana = self.conv.do(title)
            author = data.find("p", class_="artist").text
            # 任意のタブ<>で正規表現を使って区切る
            author_list = re.split(r'<.+?>', str(author))[1:-1]
            author_list = list(map(lambda x: re.split(r'[:：]', x)[-1], author_list))
            new_author_list = []
            for author_data in author_list:
                new_author_list.extend(author_data.split('・'))
            url = urljoin(load_url + '/', data.find("a")['href'])
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'author': ','.join(new_author_list),
                'raw_author': author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


    @exception
    def _crawl_shonen_jump_plus(self):
        """id:35 少年ジャンプ＋の作品一覧を取得"""
        load_url = urljoin(self.app_record.site_url, '/series')
        soup = self.get_soup(load_url)
        datas_1 = soup.find_all("li", class_="series-list-item")

        load_url = urljoin(self.app_record.site_url, '/series/finished')
        soup = self.get_soup(load_url)
        datas_2 = soup.find_all("li", class_="series-list-item")

        datas = datas_1 + datas_2
        crawled_at = datetime.datetime.now()
        for data in datas:
            title = data.find("h2", class_="series-list-title").text
            title_kana = self.conv.do(title)
            author = data.find("h3", class_="series-list-author").text
            author_list = author.split('/')
            url = data.find("a")["href"]
            self.comics.append({
                'title': title,
                'title_kana': title_kana,
                'author': ','.join(author_list),
                'raw_author': author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


    @exception
    def _crawl_ura_sunday(self):
        """id:64 裏サンデーの作品一覧を取得"""
        crawled_at = datetime.datetime.now()
        # 連載中作品
        print("連載中作品:")
        load_url = urljoin(self.app_record.site_url, '/serial_title')
        soup = self.get_soup(load_url)
        datas = soup.find("div", class_="title-all-list").find_all("li")
        for data in tqdm(datas):
            if not data.find("a"): continue
            href = data.find("a")["href"]
            url = urljoin(self.app_record.site_url, href)
            soup_comic = self.get_soup(url)

            info = soup_comic.find("div", class_="info")
            title = info.find("h1").text.strip()
            author = info.find("div", class_="author").text.strip()
            author_list = list(map(lambda x: re.split(r'[:：]', x)[-1].strip(), author.split('\u3000')))
            author_list = list(filter(bool, author_list))
            self.comics.append({
                'title': title,
                'title_kana': self.conv.do(title),
                'author': ','.join(author_list),
                'raw_author': author,
                'app_id': self.app_record.id,
                'url': url,
                'crawled_at': crawled_at,
            })


        # 完結作品
        load_url = urljoin(self.app_record.site_url, '/complete_title')
        soup = self.get_soup(load_url)

        datas = soup.find("div", class_="title-all-list").find_all("li")
        for data in datas:
            if not data.find("h2"): continue
            title = data.find("h2").text
            author = data.find("div").find("div").text
            author_list = list(map(lambda x: x.split(":")[-1].strip(), author.split('\u3000')))
            author_list = list(filter(bool, author_list))
            url = data.find("a")["href"]
            self.comics.append({
                'title': title,
                'title_kana': self.conv.do(title),
                'author': ','.join(author_list),
                'raw_author': author,
                'app_id': self.app_record.id,
                'url': urljoin(self.app_record.site_url, data.find("a")["href"]),
                'crawled_at': crawled_at,
            })
        
        # app_idをマンガワンに変更したものを追加
        app_record = App.query.filter_by(name='マンガワン').first()
        crawler = ComicCrawler(app_record)
        for comic in self.comics:
            new_comic = comic.copy()
            new_comic['app_id'] = app_record.id
            crawler.comics.append(new_comic)
        crawler.save()


    def save(self):
        # 同じアプリのcomicは削除
        delete_query = Crawl.query.filter_by(app_id=self.app_record.id)
        print(f'deleted App {self.app_record.name} {delete_query.count()} comics')
        delete_query.delete()
        db.session.commit()

        print(f'adding {len(self.comics)} comics')
        for comic in tqdm(self.comics):
            Crawl.add_crawl(comic)
        print(f'done')
        self.comics = []