from django.db import models
from django.utils import timezone


class Region(models.Model):
    """Andijon hududlari (districts)"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Hudud nomi")
    is_open = models.BooleanField(default=True, verbose_name="Qabul ochiq")
    warning_message = models.CharField(
        max_length=200, 
        default="Bu hududda qabul tugagan",
        verbose_name="Ogohlantirish xabari"
    )
    deadline = models.DateField(null=True, blank=True, verbose_name="Muddat")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    
    class Meta:
        verbose_name = "Hudud"
        verbose_name_plural = "Hududlar"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class School(models.Model):
    """Maktablar"""
    region = models.ForeignKey(
        Region, 
        on_delete=models.CASCADE, 
        related_name='schools',
        verbose_name="Hudud"
    )
    name = models.CharField(max_length=200, verbose_name="Maktab nomi")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")
    
    class Meta:
        verbose_name = "Maktab"
        verbose_name_plural = "Maktablar"
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.region.name})"


class Application(models.Model):
    """Ishtirokchilar arizalari"""
    
    GRADE_CHOICES = [
        ('7', '7-sinf'),
        ('8', '8-sinf'),
        ('9', '9-sinf'),
        ('10', '10-sinf'),
        ('11', '11-sinf'),
    ]
    
    DEVICE_CHOICES = [
        ('none', "Kompyuter yo'q"),
        ('pc', 'Shaxsiy kompyuter'),
        ('laptop', 'Noutbuk'),
    ]
    
    ENGLISH_LEVEL_CHOICES = [
        ('bilmayman', 'Bilmayman'),
        ('A1', 'A1'),
        ('A2', 'A2'),
        ('B1', 'B1'),
        ('B2', 'B2'),
        ('C1', 'C1'),
        ('C2', 'C2'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'KUTILMOQDA'),
        ('accepted', 'QABUL QILINDI'),
        ('rejected', 'RAD ETILDI'),
    ]
    
    AI_STATUS_CHOICES = [
        ('pending', 'KUTILMOQDA'),
        ('accepted', 'QABUL QILINDI'),
        ('rejected', 'RAD ETILDI'),
        ('needs_review', 'QAYTA KO\'RIB CHIQISH'),
    ]
    
    # Personal info
    full_name = models.CharField(max_length=200, verbose_name="To'liq ism familiya")
    phone = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqam")
    
    # Educational info
    region = models.ForeignKey(
        Region, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Hudud"
    )
    school = models.ForeignKey(
        School, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Maktab"
    )
    grade = models.CharField(
        max_length=2, 
        choices=GRADE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Sinf"
    )
    
    # Additional info
    about = models.TextField(null=True, blank=True, verbose_name="O'zingiz haqingizda")
    device = models.CharField(
        max_length=10, 
        choices=DEVICE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Jihozingiz"
    )
    english_level = models.CharField(
        max_length=10, 
        choices=ENGLISH_LEVEL_CHOICES,
        null=True,
        blank=True,
        verbose_name="Ingliz tili darajasi"
    )
    
    # Status
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name="Holat"
    )

    # AI Analysis Fields
    computer_skill = models.BooleanField(null=True, blank=True, verbose_name="Kompyuter savodxonligi")
    english_skill = models.BooleanField(null=True, blank=True, verbose_name="Ingliz tili")
    ai_status = models.CharField(
        max_length=15,
        choices=AI_STATUS_CHOICES,
        default='pending',
        verbose_name="AI Qarori"
    )
    ai_reason = models.TextField(null=True, blank=True, verbose_name="AI Izohi")
    description_quality = models.CharField(max_length=20, null=True, blank=True, verbose_name="AI Sifat Bahosi")
    analyzed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tahlil vaqti")
    
    # Timestamps
    telegram_user_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram ID")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")
    
    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} - {self.phone}"
    
    @property
    def is_submitted(self):
        """Check if the application has been submitted (at least region is selected)"""
        return self.region_id is not None

    def get_status_display_uz(self):
        """Get status in Uzbek for templates"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class BotUser(models.Model):
    """Telegram bot foydalanuvchilarini kuzatish"""
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=100, null=True, blank=True, verbose_name="Foydalanuvchi nomi")
    claimed_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Band qilingan raqam")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bot foydalanuvchisi"
        verbose_name_plural = "Bot foydalanuvchilari"

    def __str__(self):
        return f"{self.telegram_id} - {self.claimed_phone}"


class ApplicationStatusAudit(models.Model):
    """Immutable audit log for application status changes"""
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='status_audits',
        verbose_name="Ariza"
    )
    previous_status = models.CharField(max_length=10, verbose_name="Oldingi holat")
    new_status = models.CharField(max_length=10, verbose_name="Yangi holat")
    admin_user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Admin foydalanuvchi"
    )
    action_type = models.CharField(
        max_length=50,
        default='bulk_status_update',
        verbose_name="Amal turi"
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Vaqt")
    
    class Meta:
        verbose_name = "Holat o'zgarish tarixi"
        verbose_name_plural = "Holat o'zgarish tarixlari"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.application.full_name}: {self.previous_status} → {self.new_status}"
