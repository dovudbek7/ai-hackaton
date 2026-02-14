import requests
import time
# --- MA'LUMOTLAR ---
ESKIZ_EMAIL = 'grobo3216@gmail.com'
ESKIZ_PASSWORD = 'y15tJ8V49KZlMOhcqebSUMmxgp7OouD4tIZGHnJ0'

def get_token():
    url = "https://notify.eskiz.uz/api/auth/login"
    payload = {'email': ESKIZ_EMAIL, 'password': ESKIZ_PASSWORD}
    r = requests.post(url, data=payload)
    return r.json()['data']['token']

def send_test_sms(token, phone, name):
    url = "https://notify.eskiz.uz/api/message/sms/send"
    headers = {'Authorization': f'Bearer {token}'}
    
    # TEST MATNI
    text = f"Assalomu alaykum {name} Andijon AI Hackatonidan natijangiz e'lon qilindi ushbu link orqali kirib ko'ringishingiz mumkin: https://t.me/andijon_hackaton_bot"
    
    payload = {
        'mobile_phone': phone, # Format: 998901234567
        'message': text,
        'from': 'HACKATHON'
    }
    
    r = requests.post(url, headers=headers, data=payload)
    return r.json()

def send_bulk_sms(token, phones_names_list):
    """Send SMS to multiple recipients"""
    url = "https://notify.eskiz.uz/api/message/sms/send"
    headers = {'Authorization': f'Bearer {token}'}
    
    results = []
    for phone, name in phones_names_list:
        text = f"Assalomu alaykum {name} Andijon AI Hackatonidan natijangiz e'lon qilindi ushbu link orqali kirib ko'ringishingiz mumkin: https://t.me/andijon_hackaton_bot"
        
        payload = {
            'mobile_phone': phone,
            'message': text,
            'from': 'HACKATHON'
        }
        
        try:
            r = requests.post(url, headers=headers, data=payload)
            result = r.json()
            results.append({
                'phone': phone, 
                'name': name, 
                'status': result
            })
            print(f"✓ Sent to {name} ({phone}): {result.get('status', 'sent')}")
        except Exception as e:
            results.append({
                'phone': phone, 
                'name': name, 
                'error': str(e)
            })
            print(f"✗ Error for {name} ({phone}): {e}")
    
    return results

# ===================
# Main execution
# ===================

if __name__ == "__main__":
    # 1. Get token
    token = get_token()
    print("Token obtained successfully!")
    
    # 2. Option A: Send to one person
    my_phone = '998916200920'  # Format: 998XXXXXXXXX
    my_name = 'Dovudbek Murodov'
    
    result = send_test_sms(token, my_phone, my_name)
    print(f"Result: {result}")
    
    # OR Option B: Send to multiple people (from database)
    # Uncomment below to use:
    """
    # import django
    # import os
    # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    # django.setup()
    # from hackathon.models import Application
    
    # students = Application.objects.filter(overall_status='qabul_qilindi')
    # phones_names = [(s.phone, s.full_name) for s in students]
    # 
    # results = send_bulk_sms(token, phones_names)
    # print(f"\nTotal: {len(results)} SMS sent")
    """