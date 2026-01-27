import os
import django
import sys

# Django muhitini sozlash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from hackathon.models import Application, School, Region
from hackathon.tasks import analyze_application

def test_ai_analysis():
    print("--- AI Tahlili Testini Boshlaymiz ---")
    
    # 1. Test uchun hudud va maktab yaratish (agar yo'q bo'lsa)
    region, _ = Region.objects.get_or_create(name="Test Hududi")
    school, _ = School.objects.get_or_create(name="Test Maktabi", region=region)
    
    # 2. Test ariza yaratish
    app = Application.objects.create(
        full_name="Test User",
        phone="+998901234567",
        school=school,
        region=region,
        about="Men hackathonda ishtirok etmoqchiman. Python va Django bo'yicha bilimga egaman va yangi loyihalar yaratishni yaxshi ko'raman.",
        device='laptop',
        english_level='intermediate'
    )
    
    print(f"Ariza yaratildi (ID: {app.id})")
    
    try:
        # 3. Taskni sinxron ravishda ishga tushirish (delay emas)
        print("AI tahlili kutilmoqda...")
        analyze_application.apply(args=(app.id,))
        
        # 4. Natijani tekshirish
        app.refresh_from_db()
        print("\n--- Natijalar ---")
        print(f"Sifat: {app.description_quality}")
        print(f"Qaror: {app.decision}")
        print(f"Izoh: {app.ai_reason}")
        print(f"Vaqt: {app.analyzed_at}")
        
        if app.decision:
            print("\n✅ TEST MUVAFFAQIYATLI!")
        else:
            print("\n❌ TEST MUZOKARA QILIB BO'LMADI (Natija yo'q)")
            
    except Exception as e:
        print(f"\n❌ XATOLIK: {e}")
    finally:
        # 5. Tozalash
        # app.delete()
        # print("Test ariza o'chirildi.")
        pass

if __name__ == "__main__":
    test_ai_analysis()
