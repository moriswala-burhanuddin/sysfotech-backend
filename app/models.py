from django.db import models
from django.core.validators import EmailValidator, RegexValidator
import re
import uuid

class ContactInfo(models.Model):
    """Model to store company contact information"""
    company_name = models.CharField(max_length=200, default="Sysfotech")
    address = models.TextField(help_text="Company address")
    phone_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?[\d\s\-\(\)]+$',
                message="Phone number can contain digits, spaces, hyphens, and parentheses."
            )
        ],
        help_text="Contact phone number"
    )
    email = models.EmailField(
        validators=[EmailValidator()],
        help_text="Company email address"
    )
    slogan = models.CharField(max_length=500, help_text="Company slogan or tagline")
    website = models.URLField(blank=True, null=True, help_text="Company website URL")
    facebook = models.URLField(blank=True, null=True, help_text="Facebook page URL")
    twitter = models.URLField(blank=True, null=True, help_text="Twitter profile URL")
    linkedin = models.URLField(blank=True, null=True, help_text="LinkedIn profile URL")
    instagram = models.URLField(blank=True, null=True, help_text="Instagram profile URL")
    working_hours = models.CharField(max_length=200, default="Mon-Fri: 9:00 AM - 6:00 PM", help_text="Business hours")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Whether this contact info is currently active")

    class Meta:
        verbose_name = "Contact Information"
        verbose_name_plural = "Contact Information"

    def __str__(self):
        return f"{self.company_name} - Contact Info"


class Inquiry(models.Model):
    """Model to store customer inquiries"""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    name = models.CharField(max_length=100, help_text="Customer's full name")
    email = models.EmailField(
        validators=[EmailValidator()],
        help_text="Customer's email address"
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?[\d\s\-\(\)]+$',
                message="Phone number can contain digits, spaces, hyphens, and parentheses."
            )
        ],
        help_text="Customer's phone number (optional)"
    )
    service_needed = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Service the customer is interested in"
    )
    project_description = models.TextField(help_text="Detailed description of the project requirements")
    budget_range = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Customer's budget range"
    )
    timeline = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Expected project timeline"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        help_text="Current status of the inquiry"
    )
    source = models.CharField(
        max_length=50,
        default='website',
        help_text="How the customer found us (website, social media, referral, etc.)"
    )
    notes = models.TextField(blank=True, null=True, help_text="Internal notes about the inquiry")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    contacted_at = models.DateTimeField(blank=True, null=True, help_text="When the customer was last contacted")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inquiry"
        verbose_name_plural = "Inquiries"

    def __str__(self):
        return f"{self.name} - {self.service_needed if self.service_needed else 'General Inquiry'}"

    def clean(self):
        """Custom validation to handle phone number"""
        from django.core.exceptions import ValidationError
        
        # If phone_number is empty or just whitespace, set it to None
        if not self.phone_number or self.phone_number.strip() == "":
            self.phone_number = None
        elif self.phone_number == "+00000000000":
            # Handle the fallback value from frontend
            self.phone_number = None
        elif self.phone_number:
            # Clean the phone number by removing spaces and formatting
            cleaned = re.sub(r'[^\d\+]', '', self.phone_number)
            # Ensure it starts with + if it was there originally
            if self.phone_number.startswith('+') and not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            self.phone_number = cleaned

class Course(models.Model):
    """Model to store course details"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Student(models.Model):
    """Model to store student details created during smart checkout"""
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    magic_link_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    """Model to store payment transactions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='transactions')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_id = models.CharField(max_length=255, unique=True, help_text="Stripe PaymentIntent ID or PayPal Order ID")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        course_title = self.course.title if self.course else 'Unknown Course'
        return f"{self.student.name} - {course_title} - {self.status}"

class Enrollment(models.Model):
    """Model to store finalized course enrollments after successful payment"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    payment_id = models.CharField(max_length=255, unique=True, help_text="Stripe PaymentIntent ID or PayPal Order ID")
    payment_provider = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.name} enrolled in {self.course.title} ({self.status})"

class Coupon(models.Model):
    """Model to store discount coupon codes"""
    code = models.CharField(max_length=50, unique=True, help_text="Coupon code (e.g., CD09012)")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Discount percentage (e.g., 10.00)")
    is_active = models.BooleanField(default=True, help_text="Whether this coupon is currently active")
    max_uses = models.IntegerField(null=True, blank=True, help_text="Maximum number of times this coupon can be used (optional)")
    uses_count = models.IntegerField(default=0, help_text="Number of times this coupon has been used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.discount_percentage}%"

class CheckoutSession(models.Model):
    """Model to securely hold checkout data until payment succeeds"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    PAYMENT_PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ]

    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_provider = models.CharField(max_length=20, choices=PAYMENT_PROVIDER_CHOICES)
    payment_id = models.CharField(max_length=255, unique=True)
    magic_link_token = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} - {self.payment_provider} - {self.status}"
