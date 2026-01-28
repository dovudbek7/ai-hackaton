import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from hackathon.models import Application, School, Region
from hackathon.tasks import analyze_application

region, _ = Region.objects.get_or_create(name='Test Hududi')
school, _ = School.objects.get_or_create(name='Test Maktabi', region=region)

app = Application.objects.create(
    full_name='Test User',
    phone=f'+99890{random.randint(1000000, 9999999)}',
    school=school,
    region=region,
    about='Men hackathonda ishtirok etmoqchiman. Python va Django bilimga egaman.',
    device='laptop',
    english_level='intermediate'
)
print(f'Application created: {app.id}')

# Async call via Celery
result = analyze_application.delay(app.id)
print(f'Task sent to Celery: {result.id}')
print('Check Celery worker terminal for output!')
