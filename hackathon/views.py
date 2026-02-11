from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.contrib import messages
from django.views import View
from django.utils import timezone as dj_timezone
from .models import (
    Region,
    School,
    Application,
    Question,
    StudentTest,
    StudentAnswer,
    RegionTestControl,
)
from django.conf import settings
import requests
from .utils import generate_otp, send_sms, get_client_ip
from datetime import datetime
from django.core.cache import cache
from .services.ai_evaluator import AITestEvaluatorService


ESKIZ_AUTH_URL = "https://notify.eskiz.uz/api/auth/login"
ESKIZ_SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"

def landing_view(request):
    if request.session.get('authenticated'):
        return redirect('profile')
    return render(request, 'hackathon/landing.html')


def register_view(request):
    if request.session.get('authenticated'):
        phone = request.session.get('phone')
        if phone:
            try:
                application = Application.objects.get(phone=phone)
                if not application.is_submitted:
                    return redirect('form')
            except Application.DoesNotExist:
                pass
        return redirect('profile')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')

        # Check verification limit (Phone)
        limit_key = f"sms_limit_{phone}"
        attempts = cache.get(limit_key, 0)
        
        if attempts >= 3:
             return render(request, 'hackathon/register.html', {
                'error_message': "Ushbu raqamdan juda ko'p urinishlar amalga oshirildi. Iltimos 1 soatdan keyin urinib ko'ring"
            })

        # Check verification limit (IP)
        client_ip = get_client_ip(request)
        ip_limit_key = f"sms_ip_limit_{client_ip}"
        ip_attempts = cache.get(ip_limit_key, 0)

        if ip_attempts >= 10:
             return render(request, 'hackathon/register.html', {
                'error_message': "Sizning qurilmangizdan juda ko'p so'rovlar yuborildi. Iltimos 1 soatdan keyin urinib ko'ring"
            })

        otp = generate_otp()
        request.session['otp'] = otp
        request.session['full_name'] = full_name
        request.session['phone'] = phone

        message = (
            f"Kodni hech kimga bermang! "
            f"Andijon Ai hackaton ga kirish uchun tasdiqlash kodi: {otp}"
        )
        try:
            send_sms(phone, message)
            if attempts == 0:
                cache.set(limit_key, 1, timeout=3600)
            else:
                cache.incr(limit_key)
            if ip_attempts == 0:
                cache.set(ip_limit_key, 1, timeout=3600)
            else:
                cache.incr(ip_limit_key)
        except Exception:
            return render(request, 'hackathon/register.html', {
                'error_message': "SMS yuborishda xatolik yuz berdi"
            })
        return redirect('otp')

    return render(request, 'hackathon/register.html')


def otp_view(request):
    error_message = None

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        session_otp = request.session.get('otp')

        if not session_otp:
            error_message = "Tasdiqlash kodi muddati tugagan"
        elif entered_otp == session_otp:
            # OTP to‘g‘ri
            request.session.pop('otp', None)
            request.session['authenticated'] = True
            
            # Determine session phone
            otp_phone = request.session.get('otp_phone')
            if otp_phone:
                phone = otp_phone
                request.session['phone'] = phone
                request.session.pop('otp_phone', None)
                request.session.pop('otp_created_at', None)
            else:
                # Registration flow
                full_name = request.session.get('full_name')
                phone = request.session.get('phone')
                
                if full_name and phone:
                    # Create Application record immediately
                    application, created = Application.objects.update_or_create(
                        phone=phone,
                        defaults={'full_name': full_name}
                    )
                    request.session['application_id'] = application.id
            
            # Final redirect check for both login and registration
            if phone:
                try:
                    application = Application.objects.get(phone=phone)
                    if not application.is_submitted:
                        return redirect('form')
                except Application.DoesNotExist:
                    pass
            
            return redirect('profile')
        else:
            error_message = "Kod noto'g'ri, qayta urinib ko'ring"

    # Determine title and percentage for template
    is_login = request.session.get('otp_phone') is not None
    title = "Kirish" if is_login else "Ro‘yxatdan o‘tish"
    percentage = "100%" if is_login else "50%"

    return render(request, 'hackathon/otp_send.html', {
        'error_message': error_message,
        'title': title,
        'percentage': percentage
    })

def form_view(request):
    # Get regions for dropdown
    regions = Region.objects.all()
    
    if request.method == 'POST':
        try:
            # Get application from session
            application_id = request.session.get('application_id')
            if not application_id:
                return redirect('register')
            
            application = get_object_or_404(Application, id=application_id)
            
            # Get form data
            region_id = request.POST.get('region')
            school_id = request.POST.get('school')
            grade = request.POST.get('grade')
            about = request.POST.get('about')
            device = request.POST.get('device')
            english_level = request.POST.get('english_level')
            
            # Get region and school objects
            region = get_object_or_404(Region, id=region_id)
            school = get_object_or_404(School, id=school_id)
            
            # Check if region is open
            if not region.is_open:
                return render(request, 'hackathon/form.html', {
                    'regions': regions,
                    'error_message': region.warning_message
                })
            
            # Update application
            application.region = region
            application.school = school
            application.grade = grade
            application.about = about
            application.device = device
            application.english_level = english_level
            application.status = 'pending'
            application.overall_status = Application.OVERALL_STATUS_KUTILAYAPTI
            application.save()
            
            # Clear session partial data but keep auth
            request.session.pop('full_name', None)
            
            # Save application ID to session (already there, but ensuring consistency)
            request.session['application_id'] = application.id
            request.session['authenticated'] = True
            request.session['phone'] = application.phone
            
            # Trigger background AI analysis only if form is filled
            print(f"DEBUG: Application {application.id} saved. About length: {len(application.about or '')}")
            if application.about and len(application.about.strip()) > 5:
                try:
                    from .tasks import analyze_application
                    print(f"DEBUG: Sending to Celery queue... ID: {application.id}")
                    # Use on_commit to ensure task doesn't start before DB has saved the data
                    transaction.on_commit(lambda: analyze_application.delay(application.id))
                except Exception as e:
                    print(f"DEBUG ERROR triggering Celery: {e}")
            else:
                print(f"DEBUG: Skipping AI analysis for app {application.id} (description too short)")
            
            return redirect('profile')
            
        except IntegrityError:
            error_message = "Bu telefon raqam allaqachon ro'yxatdan o'tgan"
            return render(request, 'hackathon/form.html', {
                'regions': regions,
                'error_message': error_message
            })
    
    return render(request, 'hackathon/form.html', {'regions': regions}) 


def profile_view(request):
    """
    Profile view - requires authentication
    User must be logged in via OTP to access this page
    """
    # Check if user is authenticated
    if not request.session.get('authenticated'):
        return redirect('login')
    
    # Get phone from session
    phone = request.session.get('phone')
    if not phone:
        return redirect('login')
    
    # Get application by phone number
    try:
        application = Application.objects.get(phone=phone)
    except Application.DoesNotExist:
        # Clear invalid session
        request.session.flush()
        return redirect('login')
    
    # Block profile if not submitted
    if not application.is_submitted:
        return redirect('form')
    
    context = {
        'application': application,
        'full_name': application.full_name,
        'phone': application.phone,
        'region': application.region.name if application.region else "Belgilanmagan",
        'school': application.school.name if application.school else "Belgilanmagan",
        'grade': application.get_grade_display() if application.grade else "Belgilanmagan",
        'about': application.about or "Ma'lumot berilmagan",
        'device': application.get_device_display() if application.device else "Belgilanmagan",
        'english_level': application.get_english_level_display() if application.english_level else "Belgilanmagan",
        'status': application.status,
        'test': application.student_tests.first(),
        'can_access_test': False,
        'student_result_text': "Natija kutilmoqda",
        'show_waiting_banner': True,
    }

    if application.status in ['accepted', 'approved']:
        test_control = RegionTestControl.objects.filter(
            region=application.region, is_test_active=True
        ).exists()
        context['can_access_test'] = bool(test_control)

    test = context['test']
    if context['can_access_test'] and (not test or not test.is_submitted):
        context['show_waiting_banner'] = False

    if test and test.is_submitted:
        if test.ai_holat == StudentTest.AI_HOLAT_QABUL_QILINDI:
            context['student_result_text'] = "Qabul qilindi"
        elif test.ai_holat == StudentTest.AI_HOLAT_QABUL_QILINMADI:
            context['student_result_text'] = "Qabul qilinmadi"
    
    return render(request, 'hackathon/profile.html', context)


class SessionApplicationMixin:
    """Session-based auth/ownership guard used by test views."""

    application = None

    def _attach_application(self, request):
        if not request.session.get('authenticated'):
            return redirect('login')

        phone = request.session.get('phone')
        application_id = request.session.get('application_id')
        if not phone:
            request.session.flush()
            return redirect('login')

        try:
            app = Application.objects.get(phone=phone)
        except Application.DoesNotExist:
            request.session.flush()
            return redirect('login')

        # Additional ownership hardening: when session has application_id, enforce match.
        if application_id and int(application_id) != app.id:
            request.session.flush()
            return redirect('login')

        self.application = app
        return None

    def dispatch(self, request, *args, **kwargs):
        response = self._attach_application(request)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)


class ApprovedStudentRequiredMixin(SessionApplicationMixin):
    def dispatch(self, request, *args, **kwargs):
        response = self._attach_application(request)
        if response:
            return response

        if self.application.status not in ['accepted', 'approved']:
            messages.error(request, "Test faqat holati qabul qilingan o'quvchilar uchun ochiq.")
            return redirect('profile')

        region_test_active = RegionTestControl.objects.filter(
            region=self.application.region,
            is_test_active=True,
        ).exists()
        if not region_test_active:
            messages.error(request, "Sizning hududingiz uchun test hali faollashtirilmagan.")
            return redirect('profile')
        return View.dispatch(self, request, *args, **kwargs)


class StudentTestView(ApprovedStudentRequiredMixin, View):
    template_name = "hackathon/test_page.html"
    QUESTION_COUNT = 5

    def _ensure_questions_assigned(self, test: StudentTest) -> None:
        if test.answers.exists():
            return

        available_count = Question.objects.filter(is_active=True).count()
        if available_count < self.QUESTION_COUNT:
            return

        selected_questions = list(
            Question.objects.filter(is_active=True).order_by("?")[: self.QUESTION_COUNT]
        )
        StudentAnswer.objects.bulk_create(
            [StudentAnswer(test=test, question=question) for question in selected_questions]
        )

    def _get_or_create_test(self, lock: bool = False) -> StudentTest:
        if lock:
            test = (
                StudentTest.objects.select_related("student")
                .select_for_update()
                .filter(student=self.application)
                .first()
            )
            if test:
                return test
            try:
                return StudentTest.objects.create(student=self.application)
            except IntegrityError:
                return (
                    StudentTest.objects.select_related("student")
                    .select_for_update()
                    .get(student=self.application)
                )

        test, _ = StudentTest.objects.select_related("student").get_or_create(
            student=self.application
        )
        return test

    def get(self, request, *args, **kwargs):
        test = self._get_or_create_test()

        if not test.is_submitted:
            self._ensure_questions_assigned(test)

        answers = list(test.answers.select_related("question").order_by("id"))
        can_render_form = (not test.is_submitted) and len(answers) == self.QUESTION_COUNT

        if not test.is_submitted and not can_render_form:
            messages.error(
                request,
                f"Test hozircha mavjud emas. Kamida {self.QUESTION_COUNT} ta faol savol bo'lishi kerak.",
            )

        student_result_text = "Natija kutilmoqda"
        if test.ai_holat == StudentTest.AI_HOLAT_QABUL_QILINDI:
            student_result_text = "Qabul qilindi"
        elif test.ai_holat == StudentTest.AI_HOLAT_QABUL_QILINMADI:
            student_result_text = "Qabul qilinmadi"

        return render(
            request,
            self.template_name,
            {
                "application": self.application,
                "test": test,
                "answers": answers,
                "can_render_form": can_render_form,
                "student_result_text": student_result_text,
            },
        )

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            test = self._get_or_create_test(lock=True)

            if test.is_submitted:
                messages.info(request, "Test allaqachon yuborilgan")
                return redirect("student-test")

            answer_rows = list(
                test.answers.select_for_update().select_related("question").order_by("id")
            )
            if len(answer_rows) != self.QUESTION_COUNT:
                messages.error(request, "Test savollari to'liq shakllanmagan.")
                return redirect("student-test")

            for answer in answer_rows:
                field_name = f"answer_{answer.id}"
                user_answer = (request.POST.get(field_name) or "").strip()
                if not user_answer:
                    messages.error(request, "Barcha savollarga javob yozish majburiy.")
                    return redirect("student-test")
                answer.written_answer = user_answer

            StudentAnswer.objects.bulk_update(answer_rows, ["written_answer", "updated_at"])

            test.is_submitted = True
            test.submitted_at = dj_timezone.now()
            test.ai_holat = StudentTest.AI_HOLAT_KUTILAYAPTI
            test.save(update_fields=["is_submitted", "submitted_at", "ai_holat", "updated_at"])

        # Async evaluation (bonus mode); fallback to sync if queue is unavailable.
        try:
            from .tasks import evaluate_student_test_async

            evaluate_student_test_async.delay(test.id)
        except Exception:
            AITestEvaluatorService.evaluate_test(test.id)

        messages.success(request, "Test muvaffaqiyatli yuborildi. AI baholash jarayoni boshlandi.")
        return redirect("student-test")


def login_view(request):
    if request.session.get('authenticated'):
        phone = request.session.get('phone')
        if phone:
            try:
                application = Application.objects.get(phone=phone)
                if not application.is_submitted:
                    return redirect('form')
            except Application.DoesNotExist:
                pass
        return redirect('profile')

    if request.method == 'POST':
        phone = request.POST.get('phone')

        # Check verification limit
        limit_key = f"sms_limit_{phone}"
        attempts = cache.get(limit_key, 0)
        
        if attempts >= 3:
             return render(request, 'hackathon/login.html', {
                'error_message': "Ushbu raqamdan juda ko'p urinishlar amalga oshirildi. Iltimos 1 soatdan keyin urinib ko'ring"
            })

        # Check verification limit (IP)
        client_ip = get_client_ip(request)
        ip_limit_key = f"sms_ip_limit_{client_ip}"
        ip_attempts = cache.get(ip_limit_key, 0)

        if ip_attempts >= 10:
             return render(request, 'hackathon/login.html', {
                'error_message': "Sizning qurilmangizdan juda ko'p so'rovlar yuborildi. Iltimos 1 soatdan keyin urinib ko'ring"
            })

        try:
            application = Application.objects.get(phone=phone)

            otp = generate_otp()
            request.session['otp'] = otp
            request.session['otp_phone'] = phone
            request.session['otp_created_at'] = datetime.now().isoformat()
            request.session['application_id'] = application.id

            message = (
                f"Kodni hech kimga bermang! "
                f"Andijon Ai hackaton ga kirish uchun tasdiqlash kodi: {otp}"
            )
            try:
                send_sms(phone, message)
                if attempts == 0:
                    cache.set(limit_key, 1, timeout=3600)
                else:
                    cache.incr(limit_key)
                if ip_attempts == 0:
                    cache.set(ip_limit_key, 1, timeout=3600)
                else:
                    cache.incr(ip_limit_key)
            except Exception:
                return render(request, 'hackathon/login.html', {
                    'error_message': "SMS yuborishda xatolik yuz berdi",
                    'phone': phone
                })
            return redirect('otp')

        except Application.DoesNotExist:
            return render(request, 'hackathon/login.html', {
                'error_message': "Bu raqam bilan ro'yxatdan o'tilmagan",
                'phone': phone
            })

    return render(request, 'hackathon/login.html')



def logout_view(request):
    """
    Logout view - clears session and redirects to login
    """
    request.session.flush()
    return redirect('login')


# AJAX endpoint for schools by region
def get_schools_by_region(request, region_id):
    """Return schools for a given region as JSON"""
    schools = School.objects.filter(region_id=region_id).values('id', 'name')
    return JsonResponse(list(schools), safe=False)
