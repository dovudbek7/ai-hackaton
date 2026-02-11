import json
import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from hackathon.models import AIAnswerEvaluation, StudentTest

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    score_level: str
    short_reason: str


class AITestEvaluatorService:
    LEVEL_TO_SCORE = {
        StudentTest.LEVEL_VERY_LOW: 1,
        StudentTest.LEVEL_LOW: 2,
        StudentTest.LEVEL_MEDIUM: 3,
        StudentTest.LEVEL_HIGH: 4,
        StudentTest.LEVEL_VERY_HIGH: 5,
    }

    SCORE_TO_LEVEL = {
        1: StudentTest.LEVEL_VERY_LOW,
        2: StudentTest.LEVEL_LOW,
        3: StudentTest.LEVEL_MEDIUM,
        4: StudentTest.LEVEL_HIGH,
        5: StudentTest.LEVEL_VERY_HIGH,
    }

    @classmethod
    def _openai_client(cls):
        import openai

        return openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    @classmethod
    def evaluate_single_answer(cls, question_text: str, answer_text: str) -> EvaluationResult:
        if not settings.OPENAI_API_KEY:
            return EvaluationResult(
                score_level=StudentTest.LEVEL_MEDIUM,
                short_reason="Vaqtinchalik baholash: API ulanmagan.",
            )

        prompt = (
            "Siz qat'iy tekshiruvchisiz. Kuchsiz javobga yuqori baho bermang. "
            "Faqat JSON qaytaring: "
            "{\"score_level\":\"very_low|low|medium|high|very_high\",\"short_reason\":\"...\"}.\n\n"
            f"Savol:\n{question_text}\n\n"
            f"Talaba javobi:\n{answer_text}\n\n"
            "Baholash mezonlari: mavzuga moslik, aniqlik, mantiq, tahlil, yozuv sifati."
        )

        client = cls._openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz adolatli va qat'iy baholovchisiz. "
                        "Faqat yaroqli JSON qaytaring. Izohlar o'zbek tilida bo'lsin."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        payload = json.loads(response.choices[0].message.content)
        score_level = payload.get("score_level", StudentTest.LEVEL_LOW)
        if score_level not in cls.LEVEL_TO_SCORE:
            score_level = StudentTest.LEVEL_LOW

        short_reason = (payload.get("short_reason") or "Izoh berilmadi").strip()
        if not short_reason:
            short_reason = "Izoh berilmadi"

        return EvaluationResult(score_level=score_level, short_reason=short_reason[:500])

    @classmethod
    def get_average_score(cls, levels: list[str]) -> float:
        if not levels:
            return 0
        total = sum(cls.LEVEL_TO_SCORE[level] for level in levels)
        return total / len(levels)

    @classmethod
    def average_to_level(cls, average_score: float) -> str:
        rounded_score = int(round(average_score))
        rounded_score = max(1, min(5, rounded_score))
        return cls.SCORE_TO_LEVEL[rounded_score]

    @classmethod
    def average_to_ai_holat(cls, average_score: float) -> str:
        if average_score >= 3.0:
            return StudentTest.AI_HOLAT_QABUL_QILINDI
        return StudentTest.AI_HOLAT_QABUL_QILINMADI

    @classmethod
    def build_overall_summary(cls, answers: list, ai_sifat_bahosi: str, ai_holat: str) -> str:
        if not settings.OPENAI_API_KEY:
            return (
                "Kuchli tomonlar: javoblarda mavzuga aloqador fikrlar bor. "
                "Zaif tomonlar: ayrim javoblar chuqur tahlilsiz yozilgan. "
                "Yozma sifat: o'rtacha. Tahliliy fikrlash: o'rtacha."
            )

        compact = []
        for idx, answer in enumerate(answers, start=1):
            evaluation = getattr(answer, "ai_evaluation", None)
            level = evaluation.score_level if evaluation else "unknown"
            compact.append(
                {
                    "savol": answer.question.prompt,
                    "javob": answer.written_answer,
                    "daraja": level,
                }
            )

        prompt = (
            "Quyidagi 5 ta yozma javob bo'yicha qisqa professional umumiy xulosa yozing. "
            "Xulosa faqat o'zbek tilida bo'lsin, 3-5 gapdan iborat bo'lsin. "
            "Majburiy qamrov: kuchli tomonlar, zaif tomonlar, yozma sifat, tahliliy fikrlash darajasi.\n\n"
            f"AI holati: {ai_holat}\n"
            f"AI sifat bahosi: {ai_sifat_bahosi}\n"
            f"Ma'lumotlar: {json.dumps(compact, ensure_ascii=False)}"
        )

        client = cls._openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Siz professional o'qituvchi-assistentsiz."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        text = (response.choices[0].message.content or "").strip()
        return text[:2000] if text else "Umumiy xulosa tayyorlanmadi."

    @classmethod
    def evaluate_test(cls, test_id: int) -> None:
        with transaction.atomic():
            test = (
                StudentTest.objects.select_for_update()
                .prefetch_related("answers__question", "answers__ai_evaluation")
                .get(pk=test_id)
            )

            levels = []
            answers = list(test.answers.select_related("question"))

            for answer in answers:
                result = cls.evaluate_single_answer(
                    question_text=answer.question.prompt,
                    answer_text=answer.written_answer,
                )

                AIAnswerEvaluation.objects.update_or_create(
                    answer=answer,
                    defaults={
                        "score_level": result.score_level,
                        "short_reason": result.short_reason,
                    },
                )
                levels.append(result.score_level)

            if not levels:
                test.ai_sifat_bahosi = StudentTest.LEVEL_VERY_LOW
                test.ai_holat = StudentTest.AI_HOLAT_QABUL_QILINMADI
                test.overall_ai_summary = "Javoblar topilmadi."
            else:
                avg = cls.get_average_score(levels)
                test.ai_sifat_bahosi = cls.average_to_level(avg)
                test.ai_holat = cls.average_to_ai_holat(avg)
                answers_with_eval = list(test.answers.select_related("question", "ai_evaluation"))
                test.overall_ai_summary = cls.build_overall_summary(
                    answers=answers_with_eval,
                    ai_sifat_bahosi=test.ai_sifat_bahosi,
                    ai_holat=test.ai_holat,
                )

            test.save(update_fields=["ai_sifat_bahosi", "ai_holat", "overall_ai_summary", "updated_at"])
            logger.info("StudentTest %s evaluated with ai_holat=%s", test.pk, test.ai_holat)
