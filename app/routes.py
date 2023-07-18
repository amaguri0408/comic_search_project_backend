from flask import Flask, render_template, request, jsonify

from app import app
from app.models import App, Comic, CrawlHistory
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
    crawler.save()
    return jsonify(crawl_res['dict']), crawl_res['status_code']


@app.route('/api/comics', methods=['GET'])
def comics_api():
    comics = Comic.query.all()
    return jsonify([comic.to_dict() for comic in comics])


@app.route('/api/comics_table', methods=['GET'])
def comics_table_api():
    comics = Comic.query.all()

    # アプリの情報をデータベースから取得
    apps = App.query.all()
    app_dict = {app_record.id: app_record.name for app_record in apps}

    table_data = []
    for comic in comics:
        table_data.append({
            'title': comic.title,
            'title_kana': comic.title_kana,
            'main_author': comic.main_author,
            'sub_author': comic.sub_author,
            'url': comic.url,
            'app_name': app_dict[comic.app_id],
            'crawled_at': comic.crawled_at.strftime('%Y/%m/%d'),
        })
    return jsonify({'data': table_data})


@app.route('/api/app_status_table', methods=['GET'])
def app_status_table_api():
    apps = App.query.all()
    
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
        crawl_history = CrawlHistory.query.filter_by(app_id=app_record.id).order_by(CrawlHistory.crawled_at.desc()).first()
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

