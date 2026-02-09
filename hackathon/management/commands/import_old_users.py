import json
from django.core.management.base import BaseCommand
from hackathon.models import Application, Region, School
from django.utils import timezone
from datetime import datetime

class Command(BaseCommand):
    help = "Import oldUsers.json AND new JSON with region/school always filled"

    def handle(self, *args, **options):

        try:
            with open('oldUsers.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("oldUsers.json fayli topilmadi!"))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR("oldUsers.json faylida JSON xato!"))
            return

        status_map = {
            "KUTILMOQDA": "pending",
            "QABUL QILINDI": "accepted",
            "RAD ETILDI": "rejected"
        }

        device_map = {
            "Kompyuter yo'q": "none",
            "Shaxsiy kompyuter": "pc",
            "Noutbuk": "laptop",
            "": None,
            None: None
        }

        english_map = {
            "Bilmayman": "bilmayman",
            "A1": "A1",
            "A2": "A2",
            "B1": "B1",
            "B2": "B2",
            "C1": "C1",
            "C2": "C2",
            "": None,
            None: None
        }

        created_count = 0

        for item in data:

            # Region va School
            region_name = item.get("Hudud")
            if region_name and region_name != "-":
                region_name = region_name.strip()
                region, _ = Region.objects.get_or_create(name=region_name)
            else:
                # Agar JSONda bo‘lmasa default nom
                region, _ = Region.objects.get_or_create(name="Noma'lum hudud")

            school_name = item.get("Maktab")
            if school_name and school_name != "-":
                school_name = school_name.strip()
                school, _ = School.objects.get_or_create(name=school_name, region=region)
            else:
                # Agar bo‘lmasa default
                school, _ = School.objects.get_or_create(name="Noma'lum maktab", region=region)

            # created_at safe
            created_at = timezone.now()
            if item.get("Yaratilgan sana"):
                try:
                    created_at = datetime.strptime(item["Yaratilgan sana"], "%Y-%m-%d %H:%M")
                except:
                    pass

            # grade safe
            grade = item.get("Sinf")
            if grade:
                grade = grade.replace("-sinf", "")
            else:
                grade = None

            # Application create
            obj, created = Application.objects.get_or_create(
                phone=item.get("Telefon"),
                defaults={
                    "full_name": item.get("To'liq ism", "Noma'lum"),
                    "region": region,
                    "school": school,
                    "grade": grade,
                    "device": device_map.get(item.get("Jihozingiz")),
                    "english_level": english_map.get(item.get("Ingliz tili")),
                    "about": item.get("O'zingiz haqingizda"),
                    "status": status_map.get(item.get("Holat"), "pending"),
                    "ai_status": status_map.get(item.get("AI Holati"), "pending"),
                    "description_quality": None if item.get("AI Bahosi") in [None, "-", ""] else item.get("AI Bahosi"),
                    "ai_reason": None if item.get("AI Izohi") in [None, "-", ""] else item.get("AI Izohi"),
                    "created_at": created_at
                }
            )

            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{created_count} ta application muvaffaqiyatli import qilindi 🚀"
        ))
