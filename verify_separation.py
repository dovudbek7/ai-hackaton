import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from hackathon.models import Application
from hackathon.tasks import analyze_application
from django.utils import timezone

def verify():
    # Create a test application
    app = Application.objects.create(
        full_name="Verification User",
        phone="+998991234567",
        status="pending",
        about="I want to participate in the hackathon because I love AI."
    )
    
    print(f"Created app {app.id} with status: {app.status}")
    
    # Simulate AI analysis
    # We'll mock the OpenAI call or just check the save logic
    # Since I can't easily mock in this environment without more setup, 
    # I'll just check if the fields are updated correctly in tasks.py via review
    # and maybe run a manual update check.
    
    # Actually, I'll just check if status remains pending after a save with update_fields
    app.status = "accepted" # Manually change it in memory
    app.ai_status = "rejected"
    
    # If tasks.py does this:
    app.save(update_fields=['ai_status', 'updated_at'])
    
    # Refresh from DB
    app.refresh_from_db()
    print(f"After partial save, status in DB: {app.status}")
    print(f"After partial save, ai_status in DB: {app.ai_status}")
    
    if app.status == "pending" and app.ai_status == "rejected":
        print("SUCCESS: General status was NOT updated by partial save!")
    else:
        print("FAILURE: General status was updated or ai_status failed to update.")

    app.delete()

if __name__ == "__main__":
    verify()
