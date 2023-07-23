import time
from urllib.parse import urljoin

from sqlalchemy import func
from sqlalchemy.orm import joinedload
from flask import Flask, render_template, request, jsonify

from app import app, db
from app.models import App, Comic, Crawl, CrawlHistory
from app.crawler import ComicCrawler


@app.route('/')
def index():
    return render_template('search_v1.html')


@app.route('/app_status')
def app_status():
    dev = request.args.get('dev')
    return render_template('app_status_v1.html', dev=dev)


@app.route('/crawl', methods=['POST'])
def crawl():
    data = request.json
    app_name = data.get('app_name')
    # app_nameを検索
    app_query = App.query.filter_by(name=app_name).first()
    if app_query is None:
        return 'App not found'
    crawler = ComicCrawler(app_query)
    crawl_res = crawler.crawl()
    if crawl_res['status_code'] == 200:
        crawler.save()
    return jsonify(crawl_res['dict']), crawl_res['status_code']


@app.route('/api/comics', methods=['GET'])
def comics_api():

    data = request.args
    fifty = data.get('fifty')

    # アプリの情報をデータベースから取得
    apps = App.query.all()
    app_dict = {app_record.id: app_record.name for app_record in apps}

    if fifty:
        comics = Comic.query.filter(Comic.title_kana.like(f'{fifty}%')).options(joinedload(Comic.crawls)).all()
    else:
        comics = Comic.query.options(joinedload(Comic.crawls)).all()

    def func_comic(comic):
        res = {
            'title': comic.title,
            'title_kana': comic.title_kana,
            'author': comic.author,
            'raw_author': comic.raw_author,
            'apps': [
                {
                    'name': app_dict[crawl.app_id],
                    'url': crawl.url,
                    'crawled_at': crawl.crawled_at.strftime('%Y/%m/%d'),
                }
                for crawl in comic.crawls
            ],
        }
        return res
    table_data = list(map(func_comic, comics))
    return jsonify({'data': table_data})


@app.route('/api/comics_table', methods=['GET'])
def comics_table_api():
    comics = Comic.query.options(joinedload(Comic.crawls)).all()

    # アプリの情報をデータベースから取得
    apps = App.query.all()
    app_dict = {app_record.id: app_record.name for app_record in apps}

    def func_comic(comic):
        res = {
            'title': comic.title,
            'title_kana': comic.title_kana,
            'author': comic.author,
            'raw_author': comic.raw_author,
            'apps': [
                {
                    'app_name': app_dict[crawl.app_id],
                    'url': crawl.url,
                    'crawled_at': crawl.crawled_at.strftime('%Y/%m/%d'),
                }
                for crawl in comic.crawls
            ],
        }
        return res
    table_data = list(map(func_comic, comics))
    return jsonify({'data': table_data})


@app.route('/api/app_status_table', methods=['GET'])
def app_status_table_api():
    apps = App.query.all()

    # 各Appの最新のCrawlHistoryのidを取得
    subquery = db.session.query(
        CrawlHistory.app_id, 
        func.max(CrawlHistory.id).label('max_id')
    ).group_by(CrawlHistory.app_id).subquery()

    # 最新のCrawlHistoryのレコードを取得
    latest_crawl_histories = db.session.query(CrawlHistory).join(
        subquery, CrawlHistory.id == subquery.c.max_id
    ).all()

    crawl_history_dict = {ch.app_id: ch for ch in latest_crawl_histories}

    table_data = []
    for app_record in apps:
        record_dict = {
            'app_name': app_record.name,
            'abj_management_number': app_record.abj_management_number,
            'company_name': app_record.company_name,
            'service_type': app_record.service_type,
            'img_url': app_record.img_url,
            'url': {
                'app_store_url': app_record.app_store_url,
                'google_play_url': app_record.google_play_url,
                'site_url': app_record.site_url,
            },
        }
        if app_record.platform_type == 'app': record_dict['platform_type'] = 'アプリ'
        elif app_record.platform_type == 'web': record_dict['platform_type'] = 'Web'
        elif app_record.platform_type == 'both': record_dict['platform_type'] = 'アプリ, Web'
        else: record_dict['platform_type'] = '-'
        # CrawlHistoryから最新のデータを取得
        # crawl_history = CrawlHistory.query.filter_by(app_id=app_record.id).order_by(CrawlHistory.crawled_at.desc()).first()
        crawl_history = crawl_history_dict.get(app_record.id)
        if crawl_history is None:
            record_dict['status'] = '未対応'
            record_dict['comics_num'] = '-'
            record_dict['crawled_at'] = '-'
            record_dict['detail'] = '-'
        else:
            if crawl_history.status == 'success':
                record_dict['status'] = '取得成功'
            elif crawl_history.status == 'failure':
                record_dict['status'] = '取得失敗'
            record_dict['comics_num'] = crawl_history.comics_num
            record_dict['crawled_at'] = crawl_history.crawled_at.strftime('%Y/%m/%d %H:%M:%S')
            record_dict['detail'] = crawl_history.detail
        table_data.append(record_dict)
    
    return jsonify({'data': table_data})


@app.route('/api/app_status_4front', methods=['GET'])
def app_status_4front_api():
    """フロントのためのAPI"""
    apps = App.query.all()

    # 各Appの最新のCrawlHistoryのidを取得
    subquery = db.session.query(
        CrawlHistory.app_id, 
        func.max(CrawlHistory.id).label('max_id')
    ).group_by(CrawlHistory.app_id).subquery()

    # 最新のCrawlHistoryのレコードを取得
    latest_crawl_histories = db.session.query(CrawlHistory).join(
        subquery, CrawlHistory.id == subquery.c.max_id
    ).all()

    crawl_history_dict = {ch.app_id: ch for ch in latest_crawl_histories}
    
    table_data = []
    for app_record in apps:
        record_dict = {
            'name': app_record.name,
            'abj_management_number': app_record.abj_management_number,
            'company_name': app_record.company_name,
            'service_type': app_record.service_type,
            'img_url': urljoin(app.config['DEPLOY_URL'], app_record.img_url),
            'app_store_url': app_record.app_store_url,
            'google_play_url': app_record.google_play_url,
            'site_url': app_record.site_url,
        }
        if app_record.platform_type == 'app': record_dict['platform_type'] = 'アプリ'
        elif app_record.platform_type == 'web': record_dict['platform_type'] = 'Web'
        elif app_record.platform_type == 'both': record_dict['platform_type'] = 'アプリ, Web'
        else: record_dict['platform_type'] = '-'
        # CrawlHistoryから最新のデータを取得
        # crawl_history = CrawlHistory.query.filter_by(app_id=app_record.id).order_by(CrawlHistory.crawled_at.desc()).first()
        crawl_history = crawl_history_dict.get(app_record.id)
        if crawl_history is None:
            record_dict['status'] = '未対応'
            record_dict['comics_num'] = '-'
            record_dict['crawled_at'] = '-'
            record_dict['detail'] = '-'
        else:
            if crawl_history.status == 'success':
                record_dict['status'] = '取得成功'
            elif crawl_history.status == 'failure':
                record_dict['status'] = '取得失敗'
            record_dict['comics_num'] = crawl_history.comics_num
            record_dict['crawled_at'] = crawl_history.crawled_at.strftime('%Y/%m/%d %H:%M:%S')
            record_dict['detail'] = crawl_history.detail
        table_data.append(record_dict)
    
    return jsonify({'data': table_data})