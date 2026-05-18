
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'gym-management-secret-key-2024'
    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PASSWORD = '123456'
    DB_NAME = '健身预约平台'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
