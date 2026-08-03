import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_ujamaaflow')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///downa.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@ujamaaflow.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin@1234')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'Admin')
