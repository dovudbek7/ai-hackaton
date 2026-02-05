from django.contrib import admin
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from django.db.models import Count
from .models import Region, School, Application
from .tasks import analyze_application


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_open', 'deadline']
    list_filter = ['is_open']
    search_fields = ['name']
    list_editable = ['is_open']


def export_school_stats_xls(modeladmin, request, queryset):
    """Tanlangan maktablar bo'yicha statistikani Excelga yuklash"""
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Maktab Statistikasi"
    
    # Headers
    headers = ["Hudud", "Maktab", "Arizalar soni"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    # Annotate queryset with application count
    # We need to import Application here or use related_name if available.
    # School has related_name='schools' from Region, but for Application it is 'application_set' by default directly,
    # or actually in the Application model: school = models.ForeignKey(..., related_name='applications')?
    # Checking Application model: school = models.ForeignKey(..., related_name='applications' is NOT set, so default is application_set)
    # Actually, let's check models.py content again to be sure about related_name if any.
    # Application model: school = models.ForeignKey(School, ..., related_name='application_set' (default))
    # Wait, looking at previous file view of models.py (Step 27):
    # school = models.ForeignKey(School, ... verbose_name="Maktab")
    # So related name is default 'application_set'
    
    schools_with_counts = queryset.annotate(
        app_count=Count('application')
    ).order_by('region__name', 'name')
    
    # Write data
    for row_num, school in enumerate(schools_with_counts, 2):
        ws.cell(row=row_num, column=1, value=school.region.name)
        ws.cell(row=row_num, column=2, value=school.name)
        ws.cell(row=row_num, column=3, value=school.app_count)
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=maktab_statistikasi.xlsx'
    wb.save(response)
    return response

export_school_stats_xls.short_description = "Statistikani Excelga yuklash"


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'region', 'get_app_count']
    list_filter = ['region']
    search_fields = ['name']
    autocomplete_fields = ['region']
    actions = [export_school_stats_xls]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(app_count=Count('application'))
    
    def get_app_count(self, obj):
        return obj.app_count
    get_app_count.short_description = "Arizalar soni"
    get_app_count.admin_order_field = 'app_count'


def export_to_excel(modeladmin, request, queryset):
    """Excel faylga yuklab olish"""
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Arizalar"
    
    # Headers
    headers = [
        "ID",
        "To'liq ism",
        "Telefon",
        "Hudud",
        "Maktab",
        "Sinf",
        "Jihozingiz",
        "Ingliz tili",
        "O'zingiz haqingizda",
        "Holat",
        "AI Holati",
        "AI Bahosi",
        "AI Izohi",
        "Yaratilgan sana",
    ]
    
    # Write headers with styling
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    # Write data
    for row_num, app in enumerate(queryset, 2):
        ws.cell(row=row_num, column=1, value=app.id)
        ws.cell(row=row_num, column=2, value=app.full_name)
        ws.cell(row=row_num, column=3, value=app.phone)
        ws.cell(row=row_num, column=4, value=app.region.name if app.region else "-")
        ws.cell(row=row_num, column=5, value=app.school.name if app.school else "-")
        ws.cell(row=row_num, column=6, value=app.get_grade_display())
        ws.cell(row=row_num, column=7, value=app.get_device_display())
        ws.cell(row=row_num, column=8, value=app.get_english_level_display())
        ws.cell(row=row_num, column=9, value=app.about)
        ws.cell(row=row_num, column=10, value=app.get_status_display())
        ws.cell(row=row_num, column=11, value=app.get_ai_status_display())
        ws.cell(row=row_num, column=12, value=app.description_quality or "-")
        ws.cell(row=row_num, column=13, value=app.ai_reason or "-")
        ws.cell(row=row_num, column=14, value=app.created_at.strftime('%Y-%m-%d %H:%M'))
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Create a new sheet for statistics
    stats_ws = wb.create_sheet(title="Statistika")
    
    # Headers for stats
    stats_headers = ["Hudud", "Maktab", "Ishtirokchilar soni"]
    for col_num, header in enumerate(stats_headers, 1):
        cell = stats_ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    # Aggregate statistics from the queryset
    # We group by region name and school name and count
    stats_data = queryset.values(
        'region__name', 
        'school__name'
    ).annotate(
        count=Count('id')
    ).order_by('region__name', 'school__name')
    
    # Write stats data
    for row_num, entry in enumerate(stats_data, 2):
        stats_ws.cell(row=row_num, column=1, value=entry['region__name'] or "-")
        stats_ws.cell(row=row_num, column=2, value=entry['school__name'] or "-")
        stats_ws.cell(row=row_num, column=3, value=entry['count'])
    
    # Auto-adjust column widths for stats sheet
    for column in stats_ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        stats_ws.column_dimensions[column_letter].width = adjusted_width

    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=arizalar.xlsx'
    wb.save(response)
    return response

export_to_excel.short_description = "Excel faylga yuklab olish"


def export_to_json(modeladmin, request, queryset):
    """JSON faylga yuklab olish"""
    import json
    from django.http import HttpResponse # Ensure output is correct type
    
    data = []
    for app in queryset:
        data.append({
            "id": app.id,
            "full_name": app.full_name,
            "phone": app.phone,
            "region": app.region.name if app.region else None,
            "school": app.school.name if app.school else None,
            "grade": app.get_grade_display(),
            "device": app.get_device_display(),
            "english_level": app.get_english_level_display(),
            "about": app.about,
            "status": app.get_status_display(),
            "ai_status": app.get_ai_status_display(),
            "ai_reason": app.ai_reason,
            "description_quality": app.description_quality,
            "analyzed_at": app.analyzed_at.strftime('%Y-%m-%d %H:%M') if app.analyzed_at else None,
            "created_at": app.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename=arizalar.json'
    return response

export_to_json.short_description = "JSON faylga yuklab olish"


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'full_name', 
        'phone', 
        'region', 
        'school', 
        'status',
        'ai_status',
        'description_quality',
        'created_at'
    ]
    list_filter = ['status', 'ai_status', 'description_quality', 'region', 'grade', 'english_level', 'device', 'created_at']
    search_fields = ['full_name', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'analyzed_at']
    list_editable = ['status']
    autocomplete_fields = ['region', 'school']
    
    def run_ai_analysis(self, request, queryset):
        """AI tahlilini qo'lda ishga tushirish"""
        triggered_count = 0
        skipped_count = 0
        for app in queryset:
            if app.about and len(app.about.strip()) > 10:  # Minimum length check
                analyze_application.delay(app.id)
                triggered_count += 1
            else:
                skipped_count += 1
        
        msg = f"{triggered_count} ta ariza AI tahliliga yuborildi."
        if skipped_count > 0:
            msg += f" {skipped_count} ta ariza ma'lumot yetarli emasligi sababli o'tkazib yuborildi."
        
        self.message_user(request, msg)
    
    run_ai_analysis.short_description = "AI tahlilini ishga tushirish"
    
    actions = [export_to_excel, export_to_json, run_ai_analysis]
    
    fieldsets = (
        ('Shaxsiy ma\'lumotlar', {
            'fields': ('full_name', 'phone')
        }),
        ('Ta\'lim ma\'lumotlari', {
            'fields': ('region', 'school', 'grade')
        }),
        ('Qo\'shimcha ma\'lumotlar', {
            'fields': ('about', 'device', 'english_level')
        }),
        ('AI Tahlil', {
            'fields': (
                'ai_status', 
                'description_quality',
                'ai_reason', 
                'analyzed_at'
            )
        }),
        ('Holat', {
            'fields': ('status',)
        }),
        ('Vaqt belgilari', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
