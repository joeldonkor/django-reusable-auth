import os
import sys

# --- ADD THESE TWO LINES AT THE VERY TOP ---
# This dynamically finds your 'src' folder and adds it to Python's system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import django
from django.conf import settings
from django.test.utils import get_runner

def run_tests():
    # Configure minimal Django settings for testing your package
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',  # Runs blazing fast in RAM
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'rest_framework',        # Required since your package uses DRF
            'reusable_auth',    # Your reusable application
        ],
        AUTH_USER_MODEL='reusable_auth.CustomUser',  # Points to your package's model
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

    # Initialize Django
    django.setup()
    
    # Locate and run the tests inside the /tests folder
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=1, interactive=True)
    failures = test_runner.run_tests(['tests'])
    sys.exit(bool(failures))

if __name__ == '__main__':
    run_tests()
