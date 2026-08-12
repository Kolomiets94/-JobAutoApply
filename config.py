import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv('BOT_TOKEN')

# AI API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

# Directories
RESUME_FOLDER = 'resume'
USER_DATA_FOLDER = 'user_data'

# Create directories
os.makedirs(RESUME_FOLDER, exist_ok=True)
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# Default filters
DEFAULT_FILTERS = {
    'keywords': ['frontend', 'react', 'javascript', 'typescript', 'vue', 'angular'],
    'exclude_keywords': ['senior', 'lead', 'manager', 'director'],
    'min_salary': 0,
    'remote_only': True,
    'experience_level': 'junior',
    'cities': ['Москва', 'Санкт-Петербург', 'Удаленная работа']
}

# hh.ru API
HH_API_URL = 'https://api.hh.ru/vacancies'
HH_USER_AGENT = 'JobApplyBot/1.0 (your_email@example.com)'
