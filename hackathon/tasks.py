from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import Application, StudentTest
import openai
import json
import logging
from .services.ai_evaluator import AITestEvaluatorService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def analyze_application(self, application_id):
    print(f"\n--- DEBUG: Celery received task for Application {application_id} ---")
    try:
        application = Application.objects.get(id=application_id)
        if not application.about or len(application.about.strip()) < 5:
            print(f"--- DEBUG: Skipping Application {application_id} (Too short) ---")
            logger.info(f"Application {application_id} skipped: description too short or missing.")
            return
    except Application.DoesNotExist:
        logger.error(f"Application {application_id} topilmadi")
        return

    # O‘zbekcha, qat’iy va inklyuziv prompt
    # Muhim: F-stringlarda literal { } belgilarini {{ }} ko'rinishida yozish kerak
    prompt = f"""
Quyidagi hackathon arizasini tahlil qil.

Ariza topshiruvchi quyidagi ma’lumotlarni oldindan taqdim etgan:
- Ingliz tili darajasi: {application.get_english_level_display()}
- Jihozi: {application.get_device_display()}

Sening vazifang — arizani adolatli va inklyuziv tarzda baholash.

Baholash mezonlari:

1. description_quality (tavsif sifati):
- "high": aniq maqsad bor, texnologiya yoki o‘rganish bilan bog‘liq, yaxshi tushuntirilgan.
- "medium": ishtirok etish niyati bor, lekin tavsif qisqa yoki to‘liq aniqlanmagan.
- "low": ma’nosiz, spam yoki hackathon mavzusiga aloqasi yo‘q.

Muhim qoidalar:
- Ingliz tili darajasi va jihoz mavjudligi qarorga yordamchi sifatida ta'sir qiladi.
- Qaror ASOSIY HOLDA description_quality ga qarab qabul qilinadi.

Qaror qoidalari:
- AGAR description_quality "high" bo‘lsa → ACCEPT.
- AGAR description_quality "medium" bo‘lsa → ACCEPT.
- AGAR description_quality "low" bo‘lsa → REJECT.

Faqat JSON formatida javob qaytar:
{{
  "description_quality": "high" | "medium" | "low",
  "decision": "accepted" yoki "rejected",
  "reason": "qisqa va aniq izoh"
}}

Ariza tavsifi:
{application.about}
"""

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen hackathon arizalarini baholovchi qat’iy, adolatli va inklyuziv tizimsan. "
                        "Barcha baholash va izohlarni faqat O‘ZBEK TILIDA ber. "
                        "Faqat yaroqli JSON formatida javob qaytar."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        description_quality = result.get("description_quality")
        reason = result.get("reason")

        # 🔒 HARD BUSINESS LOGIC (AI xato qilsa ham)
        if description_quality in ["high", "medium"]:
            decision_val = "accepted"
        else:
            decision_val = "rejected"

        # Update application
        application.description_quality = description_quality
        application.ai_status = decision_val
        application.ai_reason = reason
        application.analyzed_at = timezone.now()
        
        # 🛡️ ONLY save AI-specific fields to avoid touching general status
        application.save(update_fields=[
            'description_quality', 
            'ai_status', 
            'ai_reason', 
            'analyzed_at',
            'updated_at'
        ])

        logger.info(
            f"Application {application_id} tahlil qilindi | "
            f"quality={description_quality} | decision={decision_val}"
        )

    except Exception as e:
        logger.error(f"Application {application_id} tahlilida xatolik: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def evaluate_student_test_async(self, test_id):
    try:
        test = StudentTest.objects.get(pk=test_id)
        if not test.is_submitted:
            logger.info("StudentTest %s skipped: not submitted", test_id)
            return

        AITestEvaluatorService.evaluate_test(test_id=test_id)
    except StudentTest.DoesNotExist:
        logger.error("StudentTest %s topilmadi", test_id)
    except Exception as e:
        logger.error("StudentTest %s baholashida xatolik: %s", test_id, e)
        raise self.retry(exc=e, countdown=30)


@shared_task(bind=True)
def evaluate_all_pending_tests(self, limit=100):
    """
    Barcha pending (kutilayapti) testlarni AI bilan baholash.
    
    Usage:
        - evaluate_all_pending_tests.delay() - default 100 ta
        - evaluate_all_pending_tests.delay(limit=500) - 500 ta gacha
        - evaluate_all_pending_tests.delay(limit=None) - barchasi
    """
    from django.db.models import Q
    
    # Get tests that are submitted but not yet evaluated (ai_holat = 'kutilayapti')
    queryset = StudentTest.objects.filter(
        is_submitted=True,
        ai_holat=StudentTest.AI_HOLAT_KUTILAYAPTI
    )
    
    if limit:
        queryset = queryset[:limit]
    
    test_ids = list(queryset.values_list('id', flat=True))
    total_count = len(test_ids)
    
    if total_count == 0:
        logger.info("No pending tests to evaluate")
        return {"message": "No pending tests to evaluate", "count": 0}
    
    # Queue each test for evaluation
    for test_id in test_ids:
        evaluate_student_test_async.delay(test_id)
    
    logger.info("Queued %s tests for AI evaluation", total_count)
    return {
        "message": f"{total_count} tests queued for evaluation",
        "count": total_count,
        "test_ids": test_ids[:10]  # Return first 10 for reference
    }


@shared_task(bind=True)
def evaluate_all_submitted_tests(self):
    """
    Barcha yuborilgan testlarni qayta baholash (ai_holatidan qat'i nazar).
    Faqat is_submitted=True bo'lganlarni oladi.
    
    Usage:
        - evaluate_all_submitted_tests.delay() - barcha yuborilgan testlar
    """
    queryset = StudentTest.objects.filter(is_submitted=True)
    test_ids = list(queryset.values_list('id', flat=True))
    total_count = len(test_ids)
    
    if total_count == 0:
        logger.info("No submitted tests to evaluate")
        return {"message": "No submitted tests to evaluate", "count": 0}
    
    # Queue each test for evaluation
    for test_id in test_ids:
        evaluate_student_test_async.delay(test_id)
    
    logger.info("Queued %s submitted tests for AI evaluation", total_count)
    return {
        "message": f"{total_count} submitted tests queued for re-evaluation",
        "count": total_count,
        "test_ids": test_ids[:10]
    }
