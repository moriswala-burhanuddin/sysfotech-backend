from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from app.models import ContactInfo, Inquiry , Student

# Register your models here.

@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    list_display = ['id', 'company_name', 'email', 'phone_number', 'is_active', 'created_at', 'updated_at']
    list_display_links = ['id', 'company_name']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['company_name', 'email', 'phone_number', 'address']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 25
    save_on_top = True
    fieldsets = (
        ('Basic Information', {
            'fields': ('company_name', 'slogan')
        }),
        ('Contact Details', {
            'fields': ('address', 'phone_number', 'email', 'website', 'working_hours')
        }),
        ('Social Media', {
            'fields': ('facebook', 'twitter', 'linkedin', 'instagram'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['activate_selected', 'deactivate_selected']

    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} contact info records activated successfully.')
    activate_selected.short_description = "Activate selected contact info"

    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} contact info records deactivated successfully.')
    deactivate_selected.short_description = "Deactivate selected contact info"

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'service_needed', 'status', 'source', 'created_at', 'contacted_at']
    list_display_links = ['id', 'name']
    list_filter = ['status', 'service_needed', 'source', 'created_at', 'contacted_at']
    search_fields = ['name', 'email', 'phone_number', 'project_description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']
    date_hierarchy = 'created_at'
    list_per_page = 25
    save_on_top = True
    fieldsets = (
        ('Customer Information', {
            'fields': ('name', 'email', 'phone_number')
        }),
        ('Project Details', {
            'fields': ('service_needed', 'project_description', 'budget_range', 'timeline')
        }),
        ('Status & Tracking', {
            'fields': ('status', 'source', 'contacted_at', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_as_contacted', 'mark_as_in_progress', 'mark_as_completed', 'mark_as_cancelled']

    def mark_as_contacted(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='contacted', contacted_at=timezone.now())
        self.message_user(request, f'{updated} inquiries marked as contacted.')
    mark_as_contacted.short_description = "Mark selected inquiries as contacted"

    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} inquiries marked as in progress.')
    mark_as_in_progress.short_description = "Mark selected inquiries as in progress"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} inquiries marked as completed.')
    mark_as_completed.short_description = "Mark selected inquiries as completed"

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} inquiries marked as cancelled.')
    mark_as_cancelled.short_description = "Mark selected inquiries as cancelled"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Student._meta.fields]
    list_per_page = 25
    save_on_top = True
