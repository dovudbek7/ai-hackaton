import json
from django.core.management.base import BaseCommand
from hackathon.models import Application, Region, School
from django.utils import timezone
from datetime import datetime


class Command(BaseCommand):
    help = "Import applications from JSON file safely"

    def handle(self, *args, **options):

        # JSON faylni o‘qish
        try:
            with open('applications.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("applications.json fayli topilmadi!"))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR("applications.json faylida JSON xato!"))
            return

        # Mappinglar
        status_map = {
            "KUTILMOQDA": "pending",
            "QABUL QILINDI": "accepted",
            "RAD ETILDI": "rejected"
        }

        device_map = {
            "Kompyuter yo'q": "none",
            "Shaxsiy kompyuter": "pc",
            "Noutbuk": "laptop"
        }

        english_map = {
            "Bilmayman": "bilmayman",
            "A1": "A1",
            "A2": "A2",
            "B1": "B1",
            "B2": "B2",
            "C1": "C1",
            "C2": "C2"
        }

        created_count = 0

        for item in data:

            # region va school safe
            region_name = item.get("region")
            if region_name:
                region_name = region_name.strip()
            else:
                region_name = "Noma'lum hudud"

            school_name = item.get("school")
            if school_name:
                school_name = school_name.strip()
            else:
                school_name = "Noma'lum maktab"

            # Region va School topish/yaratish
            region, _ = Region.objects.get_or_create(name=region_name)
            school, _ = School.objects.get_or_create(name=school_name, region=region)

            # created_at safe
            created_at = None
            if item.get("created_at"):
                try:
                    created_at = datetime.strptime(item["created_at"], "%Y-%m-%d %H:%M")
                except:
                    created_at = timezone.now()
            else:
                created_at = timezone.now()

            # grade safe
            grade = item.get("grade")
            if grade:
                grade = grade.replace("-sinf", "")
            else:
                grade = None

            # Application yaratish
            obj, created = Application.objects.get_or_create(
                phone=item.get("phone"),
                defaults={
                    "full_name": item.get("full_name", "Noma'lum"),
                    "region": region,
                    "school": school,
                    "grade": grade,
                    "device": device_map.get(item.get("device")),
                    "english_level": english_map.get(item.get("english_level")),
                    "about": item.get("about"),
                    "status": status_map.get(item.get("status"), "pending"),
                    "ai_status": "pending",
                    "created_at": created_at
                }
            )

            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{created_count} ta application muvaffaqiyatli import qilindi 🚀"
        ))
