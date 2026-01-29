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
        application.decision = decision_val
        application.ai_reason = reason
        application.analyzed_at = timezone.now()
        application.save()

        logger.info(
            f"Application {application_id} tahlil qilindi | "
            f"quality={description_quality} | decision={decision_val}"
        )

    except Exception as e:
        logger.error(f"Application {application_id} tahlilida xatolik: {e}")
        raise self.retry(exc=e, countdown=60)
