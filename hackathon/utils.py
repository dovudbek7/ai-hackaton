import random
import requests
from django.conf import settings

def generate_otp():
    """Generates a 6-digit random OTP."""
    return str(random.randint(100000, 999999))

def send_sms(phone, message):
    """
    Sends SMS via Eskiz.uz API.
    Required settings: ESKIZ_EMAIL, ESKIZ_PASSWORD
    Optional settings: LINKSMS_SENDER (defaults to '4546')
    """
    # Normalize phone: +998901234567 -> 998901234567
    clean_phone = phone.replace('+', '').replace(' ', '').replace('(', '').replace(')', '').replace('-', '')
    
    # 1. Get Token
    auth_url = "https://notify.eskiz.uz/api/auth/login"
    auth_data = {
        'email': settings.ESKIZ_EMAIL,
        'password': settings.ESKIZ_PASSWORD
    }
    
    try:
        auth_response = requests.post(auth_url, data=auth_data)
        auth_response.raise_for_status()
        token = auth_response.json().get('data', {}).get('token')
        
        if not token:
            raise Exception("Failed to get Eskiz token")
            
        # 2. Send SMS
        send_url = "https://notify.eskiz.uz/api/message/sms/send"
        headers = {
            'Authorization': f"Bearer {token}"
        }
        
        sender = getattr(settings, 'LINKSMS_SENDER', '4546')
        
        send_data = {
            'mobile_phone': clean_phone,
            'message': message,
            'from': sender,
        }
        
        send_response = requests.post(send_url, headers=headers, data=send_data)
        send_response.raise_for_status()
        return send_response.json()
        
    except Exception as e:
        print(f"SMS sending error: {e}")
        # Re-raise so views can handle error messaging
        raise e
