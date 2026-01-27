from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import IntegrityError
from .models import Region, School, Application
from django.conf import settings
import requests
from .utils import generate_otp, send_sms
from datetime import datetime


ESKIZ_AUTH_URL = "https://notify.eskiz.uz/api/auth/login"
ESKIZ_SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"

def landing_view(request):
    if request.session.get('authenticated'):
        return redirect('profile')
    return render(request, 'hackathon/landing.html')


def register_view(request):
    if request.session.get('authenticated'):
        return redirect('profile')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')

        # Existing user → auto login
        if Application.objects.filter(phone=phone).exists():
            application = Application.objects.get(phone=phone)
            request.session['authenticated'] = True
            request.session['phone'] = phone
            request.session['application_id'] = application.id
            return redirect('profile')

        # Generate OTP
        otp = generate_otp()

        # Save to session
        request.session['otp'] = otp
        request.session['full_name'] = full_name
        request.session['phone'] = phone

        # SMS text
        message = (
            f"Kodni hech kimga bermang! "
            f"Andijon Ai hackaton ga kirish uchun tasdiqlash kodi: {otp}"
        )

        # Send SMS
        try:
            send_sms(phone, message)
        except Exception as e:
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
            
            # Check if it was a login
            otp_phone = request.session.get('otp_phone')
            if otp_phone:
                request.session['phone'] = otp_phone
                request.session.pop('otp_phone', None)
                request.session.pop('otp_created_at', None)
                return redirect('profile')
            
            # If not login, it's registration
            return redirect('form')
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
            # Get data from session
            full_name = request.session.get('full_name')
            phone = request.session.get('phone')
            
            if not full_name or not phone:
                return redirect('register')
            
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
            
            # Create application
            application = Application.objects.create(
                full_name=full_name,
                phone=phone,
                region=region,
                school=school,
                grade=grade,
                about=about,
                device=device,
                english_level=english_level,
                status='pending'  # Default status
            )
            
            # Clear session
            request.session.flush()
            
            # Save application ID to new session
            # Save application ID to new session
            request.session['application_id'] = application.id
            request.session['authenticated'] = True
            request.session['phone'] = phone
            
            # Trigger background AI analysis
            try:
                from .tasks import analyze_application
                analyze_application.delay(application.id)
            except Exception as e:
                # Log error but don't fail the request
                print(f"Failed to trigger AI analysis task: {e}")
            
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
    
    context = {
        'application': application,
        'full_name': application.full_name,
        'phone': application.phone,
        'region': application.region.name,
        'school': application.school.name,
        'grade': application.get_grade_display(),
        'about': application.about,
        'device': application.get_device_display(),
        'english_level': application.get_english_level_display(),
        'status': application.status,
    }
    
    return render(request, 'hackathon/profile.html', context)


def login_view(request):
    if request.session.get('authenticated'):
        return redirect('profile')

    if request.method == 'POST':
        phone = request.POST.get('phone')

        try:
            application = Application.objects.get(phone=phone)

            # Generate OTP
            otp = generate_otp()

            # Save OTP info in session
            request.session['otp'] = otp
            request.session['otp_phone'] = phone
            request.session['otp_created_at'] = datetime.now().isoformat()
            request.session['application_id'] = application.id

            # SMS text
            message = (
                f"Kodni hech kimga bermang! "
                f"Andijon Ai hackaton ga kirish uchun tasdiqlash kodi: {otp}"
            )

            try:
                send_sms(phone, message)
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
