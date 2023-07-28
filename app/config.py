from os import getenv

DEBUG = True
SQLALCHEMY_DATABASE_URI = getenv('RAILWAY_MYSQL_URL')
SQLALCHEMY_TRACK_MODIFICATIONS = True

CORS_ORIGINS = ["*"]

APP_CSV_PATH = 'app_info.csv'

DEPLOY_URL = 'https://comicsearchprojectbackend-production.up.railway.app/'