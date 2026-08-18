from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from app.models import ContactInfo, Inquiry, Student, Coupon, CheckoutSession, Course, Enrollment, Transaction 

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


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ['payment_id', 'created_at', 'updated_at']

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ['payment_id', 'created_at']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'phone_number', 'created_at']
    search_fields = ['name', 'email', 'phone_number']
    readonly_fields = ['magic_link_token', 'created_at', 'updated_at']
    list_filter = ['created_at']
    inlines = [EnrollmentInline, TransactionInline]
    list_per_page = 25
    save_on_top = True

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'price', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['price', 'is_active']
    list_per_page = 25

from app.models import ContactInfo, Inquiry, Student, Coupon, CheckoutSession, Course, Enrollment, Transaction, PaymentInstallment

class PaymentInstallmentInline(admin.TabularInline):
    model = PaymentInstallment
    extra = 0
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'total_amount', 'amount_paid', 'amount_remaining', 'status', 'payment_provider', 'payment_plan_badge', 'created_at']
    list_filter = ['status', 'payment_provider', 'payment_plan', 'created_at', 'course']
    search_fields = ['student__name', 'student__email', 'payment_id']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PaymentInstallmentInline]
    list_per_page = 25

    def payment_plan_badge(self, obj):
        if obj.payment_plan == 'full':
            return mark_safe('<span style="background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Full Payment</span>')
        return mark_safe('<span style="background-color: #fef08a; color: #854d0e; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Installments</span>')
    payment_plan_badge.short_description = "Payment Plan"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'amount', 'status', 'payment_method', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['student__name', 'student__email', 'payment_id']
    readonly_fields = ['created_at']
    list_per_page = 25

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_percentage', 'is_active', 'uses_count', 'max_uses', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['code']
    readonly_fields = ['uses_count', 'created_at', 'updated_at']
    list_per_page = 25

@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'email', 'name', 'course', 'amount', 'payment_provider', 'payment_plan_badge', 'status', 'created_at']
    list_filter = ['status', 'payment_provider', 'payment_plan', 'created_at']
    search_fields = ['email', 'name', 'session_id', 'payment_id']
    readonly_fields = ['session_id', 'magic_link_token', 'created_at', 'updated_at']
    list_per_page = 25

    def payment_plan_badge(self, obj):
        if obj.payment_plan == 'full':
            return mark_safe('<span style="background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Full Payment</span>')
        return mark_safe('<span style="background-color: #fef08a; color: #854d0e; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Installments</span>')
    payment_plan_badge.short_description = "Payment Plan"

@admin.register(PaymentInstallment)
class PaymentInstallmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'enrollment', 'amount', 'due_date', 'status_badge', 'created_at']
    list_filter = ['status', 'due_date', 'created_at']
    search_fields = ['name', 'enrollment__student__name', 'enrollment__student__email', 'payment_id']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    
    def status_badge(self, obj):
        if obj.status == 'paid':
            return mark_safe('<span style="background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Paid</span>')
        elif obj.status == 'overdue':
            return mark_safe('<span style="background-color: #fee2e2; color: #b91c1c; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Overdue</span>')
        return mark_safe('<span style="background-color: #fef08a; color: #854d0e; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">Pending</span>')
    status_badge.short_description = "Status"

