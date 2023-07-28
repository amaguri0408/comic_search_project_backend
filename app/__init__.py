from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import pymysql
pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.config.from_object('app.config')
CORS(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models