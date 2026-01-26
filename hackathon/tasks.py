from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import Application
import openai
import json
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def analyze_application(self, application_id):
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        logger.error(f"Application {application_id} not found")
        return

    # Use strict prompt
    prompt = f"""
    Analyze the following application description for a hackathon.
    Determine:
    1. Does the applicant have computer skills? (true/false)
    2. Does the applicant have English language skills? (true/false)
    
    Description:
    {application.about}
    
    Rules for decision:
    - ACCEPT if AND ONLY IF both computer_skill AND english_skill are true.
    - Otherwise REJECT.
    
    Return JSON ONLY:
    {{
        "computer_skill": true/false,
        "english_skill": true/false,
        "decision": "accepted" or "rejected",
        "reason": "short explanation"
    }}
    """
    
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Or gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "You are a strict application decision engine. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,  # Deterministic
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content
        result = json.loads(result_content)
        
        # Update application
        application.computer_skill = result.get('computer_skill')
        application.english_skill = result.get('english_skill')
        
        # Ensure decision is lowercase to match choices
        decision_val = result.get('decision', '').lower()
        if decision_val not in ['accepted', 'rejected']:
             # Fallback if AI hallucinates a different string, though prompt says strictly accepted/rejected
             # If strict rules say accept only if both are true:
             if application.computer_skill and application.english_skill:
                 decision_val = 'accepted'
             else:
                 decision_val = 'rejected'
        
        application.decision = decision_val
        
        # Also update the main status to match decision
        application.status = decision_val
            
        application.ai_reason = result.get('reason')
        application.analyzed_at = timezone.now()
        application.save()
        
        logger.info(f"Analyzed application {application_id}: {decision_val}")
        
    except Exception as e:
        logger.error(f"Error analyzing application {application_id}: {e}")
        # Retry in 60 seconds
        raise self.retry(exc=e, countdown=60)
