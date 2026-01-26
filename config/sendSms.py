import requests
from django.conf import settings

payload = {
    "login": settings.LINKSMS_LOGIN,
    "password": settings.LINKSMS_PASSWORD,
    "sender": settings.LINKSMS_SENDER,
    "phone": "998901234567",  # O'ZINGNI NOMERING
    "text": "Test SMS from Django 🚀"
}

r = requests.post(settings.LINKSMS_URL, json=payload, timeout=10)

print(r.status_code)
print(r.text)
