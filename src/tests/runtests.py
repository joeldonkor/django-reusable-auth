from datetime import timedelta
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
        SECRET_KEY='test-secret-key-not-for-production',  # Required by simplejwt to sign tokens
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
            'rest_framework_simplejwt.token_blacklist',  # Optional: If you want to use token blacklisting

        ],
        ROOT_URLCONF='reusable_auth.urls',  # Exposes the package's endpoints to the test client
        AUTH_USER_MODEL='reusable_auth.CustomUser',  # Points to your package's model
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        AUTH_PASSWORD_VALIDATORS=[
            {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
            {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
            {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
            {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
        ],
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],  # Fast hashing for tests only

        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': ( 
                'rest_framework_simplejwt.authentication.JWTAuthentication',

            ),  
        },
        
        SIMPLE_JWT = {
            'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
            'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
            'ROTATE_REFRESH_TOKENS': True,
            'BLACKLIST_AFTER_ROTATION': True,
            'UPDATE_LAST_LOGIN': True,
            'AUTH_HEADER_TYPES': ('Bearer',),
        }
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
