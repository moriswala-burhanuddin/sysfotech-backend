import os
import sys
from sysfotech.wsgi import application

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sysfotech.settings')
