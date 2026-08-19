from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework   import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import ContactInfo, Inquiry
from .serializers import ContactInfoSerializer, InquirySerializer, ContactInfoPublicSerializer, CourseRegistrationSerializer
from django.views.generic import TemplateView
from django.http import HttpResponse
from rest_framework.views import APIView
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
import os
import io
from django.conf import settings
import stripe
from .models import Course, Student, Transaction, Enrollment, Coupon, CheckoutSession

# ─── PDF Invoice Generator ──────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.styles import getSampleStyleSheet
from django.core.mail import EmailMessage


def generate_invoice_pdf(enrollment):
    """Generate a professional PDF invoice for a given enrollment. Returns bytes."""
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # ── Colors ──
    brand_orange = HexColor('#F97316')
    dark = HexColor('#1E293B')
    muted = HexColor('#64748B')
    light_bg = HexColor('#F8FAFC')
    green = HexColor('#16A34A')
    border_color = HexColor('#E2E8F0')

    # ── Background strip at top ──
    c.setFillColor(dark)
    c.rect(0, height - 100, width, 100, fill=True, stroke=False)

    # ── Company name in header ──
    c.setFillColor(HexColor('#FFFFFF'))
    c.setFont('Helvetica-Bold', 22)
    c.drawString(40, height - 50, 'Sysfotech IT Services')
    c.setFont('Helvetica', 9)
    c.setFillColor(HexColor('#94A3B8'))
    c.drawString(40, height - 68, '124 City Road, London, EC1V 2NX, United Kingdom')
    c.drawString(40, height - 80, 'billing@sysfotech.uk  |  +44 74421 93577')

    # ── INVOICE label ──
    c.setFillColor(brand_orange)
    c.setFont('Helvetica-Bold', 28)
    c.drawRightString(width - 40, height - 50, 'INVOICE')
    c.setFillColor(HexColor('#94A3B8'))
    c.setFont('Helvetica', 10)
    inv_number = f'INV-{enrollment.id:05d}'
    c.drawRightString(width - 40, height - 68, inv_number)

    # ── Status badge ──
    if enrollment.status == 'paid':
        c.setFillColor(green)
        c.roundRect(width - 100, height - 90, 60, 18, 4, fill=True, stroke=False)
        c.setFillColor(HexColor('#FFFFFF'))
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(width - 70, height - 85, 'PAID')

    y = height - 140

    # ── Billed To / Invoice Details ──
    c.setFillColor(muted)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(40, y, 'BILLED TO')
    c.drawString(300, y, 'INVOICE DETAILS')

    y -= 18
    c.setFillColor(dark)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(40, y, enrollment.student.name)
    c.setFont('Helvetica', 10)
    c.setFillColor(muted)

    c.setFont('Helvetica', 10)
    c.drawString(300, y, f'Date: {enrollment.created_at.strftime("%d %b %Y")}')
    y -= 16
    c.drawString(40, y, enrollment.student.email)
    c.drawString(300, y, f'Payment ID: {enrollment.payment_id[:20]}...' if len(enrollment.payment_id) > 20 else f'Payment ID: {enrollment.payment_id}')
    y -= 16
    if enrollment.student.phone_number:
        c.drawString(40, y, f'Phone: {enrollment.student.phone_number}')
    c.drawString(300, y, f'Provider: {enrollment.payment_provider.title()}')

    y -= 40

    # ── Table Header ──
    c.setFillColor(light_bg)
    c.rect(30, y - 5, width - 60, 22, fill=True, stroke=False)
    c.setStrokeColor(border_color)
    c.line(30, y - 5, width - 30, y - 5)

    c.setFillColor(dark)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(40, y + 2, 'DESCRIPTION')
    c.drawString(340, y + 2, 'QTY')
    c.drawString(400, y + 2, 'UNIT PRICE')
    c.drawRightString(width - 40, y + 2, 'TOTAL')

    y -= 30

    # ── Table Row ──
    c.setFillColor(dark)
    c.setFont('Helvetica', 10)
    c.drawString(40, y, enrollment.course.title)
    c.drawString(350, y, '1')
    c.drawString(400, y, f'£{enrollment.amount:.2f}')
    c.drawRightString(width - 40, y, f'£{enrollment.amount:.2f}')

    c.setStrokeColor(border_color)
    c.line(30, y - 12, width - 30, y - 12)

    y -= 50

    # ── Totals ──
    c.setFillColor(muted)
    c.setFont('Helvetica', 10)
    c.drawString(380, y, 'Subtotal')
    c.setFillColor(dark)
    c.drawRightString(width - 40, y, f'£{enrollment.amount:.2f}')
    y -= 18
    c.setFillColor(muted)
    c.drawString(380, y, 'VAT (0%)')
    c.setFillColor(dark)
    c.drawRightString(width - 40, y, '£0.00')

    y -= 5
    c.setStrokeColor(border_color)
    c.line(370, y, width - 30, y)
    y -= 20

    c.setFillColor(dark)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(380, y, 'Total')
    c.drawRightString(width - 40, y, f'£{enrollment.amount:.2f}')

    # ── Footer ──
    c.setFillColor(muted)
    c.setFont('Helvetica', 8)
    c.drawCentredString(width / 2, 50, 'Thank you for your purchase! If you have questions, contact billing@sysfotech.uk')
    c.drawCentredString(width / 2, 38, f'© {enrollment.created_at.year} Sysfotech IT Services. All rights reserved.')

    c.save()
    buf.seek(0)
    return buf.read()


def send_invoice_email(enrollment):
    """Generate PDF invoice and send it as an email attachment."""
    pdf_bytes = generate_invoice_pdf(enrollment)
    inv_number = f'INV-{enrollment.id:05d}'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
    magic_link_url = f'{settings.FRONTEND_URL}/verify?token={enrollment.student.magic_link_token}'

    email = EmailMessage(
        subject=f'Your Invoice {inv_number} - Sysfotech',
        body=(
            f'Hello {enrollment.student.name},\n\n'
            f'Thank you for enrolling in {enrollment.course.title}!\n\n'
            f'Your invoice {inv_number} is attached as a PDF.\n\n'
            f'Access your student dashboard here:\n{magic_link_url}\n\n'
            f'Best regards,\nSysfotech IT Services'
        ),
        from_email=from_email,
        to=[enrollment.student.email],
    )
    email.attach(f'{inv_number}.pdf', pdf_bytes, 'application/pdf')
    email.send(fail_silently=False)
    
    # Send separate admin notification
    try:
        send_admin_payment_notification(enrollment)
    except Exception as e:
        print(f"Error sending admin payment notification: {e}")

def send_installment_receipt_email(installment):
    """Send an email receipt for a successful auto-pay installment."""
    enrollment = installment.enrollment
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
    magic_link_url = f'{settings.FRONTEND_URL}/verify?token={enrollment.student.magic_link_token}'

    email = EmailMessage(
        subject=f'Payment Receipt: {installment.name} - Sysfotech',
        body=(
            f'Hello {enrollment.student.name},\n\n'
            f'We successfully processed your payment of £{installment.amount} for {installment.name} of {enrollment.course.title}!\n\n'
            f'Thank you for continuing your learning journey with us.\n\n'
            f'Access your student dashboard here:\n{magic_link_url}\n\n'
            f'Best regards,\nSysfotech IT Services'
        ),
        from_email=from_email,
        to=[enrollment.student.email],
    )
    email.send(fail_silently=False)
    
    # Send separate admin notification
    try:
        send_admin_installment_notification(installment, 'SUCCESS')
    except Exception as e:
        print(f"Error sending admin installment notification: {e}")

def send_installment_failed_email(installment):
    """Send an email warning for a failed auto-pay installment."""
    enrollment = installment.enrollment
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
    magic_link_url = f'{settings.FRONTEND_URL}/verify?token={enrollment.student.magic_link_token}'

    email = EmailMessage(
        subject=f'Action Required: Payment Failed for {installment.name} - Sysfotech',
        body=(
            f'Hello {enrollment.student.name},\n\n'
            f'We attempted to process your auto-pay installment of £{installment.amount} for {installment.name} of {enrollment.course.title}, but the charge was declined.\n\n'
            f'Please access your student dashboard to update your payment method or contact us for support:\n{magic_link_url}\n\n'
            f'Best regards,\nSysfotech IT Services'
        ),
        from_email=from_email,
        to=[enrollment.student.email],
    )
    email.send(fail_silently=False)
    
    # Send separate admin notification
    try:
        send_admin_installment_notification(installment, 'FAILED')
    except Exception as e:
        print(f"Error sending admin installment failed notification: {e}")

def send_admin_payment_notification(enrollment):
    """Send a dedicated email to the admin with full student and payment details."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
    admin_email = 'info@sysfotech.uk'
    
    subject = f'New Payment Received: {enrollment.course.title}'
    body = (
        f"A new payment has been processed!\n\n"
        f"Student Details:\n"
        f"Name: {enrollment.student.name}\n"
        f"Email: {enrollment.student.email}\n"
        f"Phone: {getattr(enrollment.student, 'phone_number', 'N/A')}\n\n"
        f"Enrollment Details:\n"
        f"Course: {enrollment.course.title}\n"
        f"Payment Plan: {enrollment.payment_plan}\n"
        f"Amount Paid: £{enrollment.amount_paid}\n"
        f"Amount Remaining: £{enrollment.amount_remaining}\n"
    )
    email = EmailMessage(subject=subject, body=body, from_email=from_email, to=[admin_email])
    email.send(fail_silently=False)

def send_admin_installment_notification(installment, status):
    """Send a dedicated email to the admin about an installment status."""
    enrollment = installment.enrollment
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
    admin_email = 'info@sysfotech.uk'
    
    subject = f'Installment {status.capitalize()}: {enrollment.student.name}'
    body = (
        f"An auto-pay installment was processed with status: {status.upper()}.\n\n"
        f"Student Details:\n"
        f"Name: {enrollment.student.name}\n"
        f"Email: {enrollment.student.email}\n\n"
        f"Installment Details:\n"
        f"Course: {enrollment.course.title}\n"
        f"Installment Name: {installment.name}\n"
        f"Amount: £{installment.amount}\n"
        f"Status: {status}\n"
    )
    email = EmailMessage(subject=subject, body=body, from_email=from_email, to=[admin_email])
    email.send(fail_silently=False)

# Create your views here.

def home_page(request):
    """Serve the React application - handles all non-admin/non-api routes"""
    return render(request, 'index.html')

class ReactAppView(TemplateView):
    """
    Custom view to handle React Router routes.
    Serves index.html for all routes that don't match admin or API patterns.
    """
    template_name = 'index.html'
    
    def get(self, request, *args, **kwargs):
        # Check if the request is for a static file or admin/api
        path = request.path_info.lstrip('/')
        
        # If it's admin, api, static, or media, let Django handle it normally
        if path.startswith(('admin/', 'api/', 'static/', 'media/', 'assets/')):
            return super().get(request, *args, **kwargs)
        
        # For all other routes, serve the React app
        return super().get(request, *args, **kwargs)

class ReactRouterView(TemplateView):
    """
    Custom view to handle React Router routes.
    Serves index.html for all routes that don't match admin or API patterns.
    """
    template_name = 'index.html'
    
    def get(self, request, *args, **kwargs):
        # Check if the request is for a static file
        path = request.path_info.lstrip('/')
        
        # If it's a static file, let Django handle it normally
        if path.startswith(('static/', 'media/', 'assets/', 'admin/', 'api/')):
            return super().get(request, *args, **kwargs)
        
        # For all other routes, serve the React app
        return super().get(request, *args, **kwargs)

class ContactInfoViewSet(viewsets.ModelViewSet):
    queryset = ContactInfo.objects.filter(is_active=True)
    serializer_class = ContactInfoSerializer
    permission_classes = []  # No authentication required - public access
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['company_name', 'email', 'phone_number']

    def get_serializer_class(self):
        if self.action == 'list' or self.action == 'retrieve':
            return ContactInfoPublicSerializer
        return ContactInfoSerializer

    @action(detail=False, methods=['get'])
    def public(self, request):
        """Get public contact information"""
        contact_info = ContactInfo.objects.filter(is_active=True).first()
        if contact_info:
            serializer = ContactInfoPublicSerializer(contact_info)
            return Response(serializer.data)
        return Response({'error': 'No active contact information found'}, status=status.HTTP_404_NOT_FOUND)

class InquiryViewSet(viewsets.ModelViewSet):
    queryset = Inquiry.objects.all().order_by('-created_at')
    serializer_class = InquirySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'service_needed', 'source']
    search_fields = ['name', 'email', 'phone_number', 'project_description']
    ordering_fields = ['created_at', 'status']

    def get_permissions(self):
        """Allow public access for creating inquiries, require authentication for other operations"""
        if self.action == 'create':
            return []  # No authentication required for creating inquiries
        return [IsAuthenticated()]  # Authentication required for other operations

    def create(self, request, *args, **kwargs):
        """Create a new inquiry"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Inquiry submitted successfully! We will contact you soon.',
                    'data': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                # Log validation errors for debugging
                print(f"Validation errors: {serializer.errors}")
                return Response({
                    'error': 'Validation failed',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log any unexpected errors
            print(f"Error creating inquiry: {str(e)}")
            return Response({
                'error': 'An unexpected error occurred',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update inquiry status"""
        inquiry = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(Inquiry.STATUS_CHOICES):
            inquiry.status = new_status
            inquiry.save()
            serializer = self.get_serializer(inquiry)
            return Response(serializer.data)
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

class CourseRegistrationView(APIView):
    permission_classes = [] # Public access

    def post(self, request):
        serializer = CourseRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # 1. Send Email to Admissions (info@sysfotech.uk)
        admissions_email = "info@sysfotech.uk"
        subject_admissions = f"New Course Registration - {data['fullName']}"
        
        # Format registration details for admissions
        details_txt = f"""
New Course Registration Received

STUDENT DETAILS:
Name: {data['fullName']}
Email: {data['email']}
Phone (WhatsApp): {data['mobile']}
Date of Birth: {data.get('dateOfBirth') or 'N/A'}
Current Address: {data.get('address') or 'N/A'}
City: {data.get('city') or 'N/A'}
Postcode: {data.get('postcode') or 'N/A'}

EMPLOYMENT DETAILS:
Status: {', '.join(data.get('currentStatus') or []) or 'N/A'}
Company Name: {data.get('companyName') or 'N/A'}
Current Job Role: {data.get('jobRole') or 'N/A'}

COURSE PREFERENCES:
Selected Course(s): {', '.join(data['selectedCourses'])}
Learning Mode: {data.get('learningMode') or 'N/A'}
Course Duration: {data.get('courseDuration') or 'N/A'}
Experience Level: {data.get('experienceLevel') or 'N/A'}

ABOUT STUDENT:
Reasons for enrolling: {', '.join(data.get('reasons') or []) or 'N/A'}
Hear about us: {', '.join(data.get('hearAboutUs') or []) or 'N/A'}

FREE DEMO DETAILS:
Registered for Demo: {data.get('wantDemo') or 'N/A'}
Demo Batch Option: {data.get('demoBatch') or 'N/A'}
Preferred Time: {data.get('demoTime') or 'N/A'}

Consent Approved: {'Yes' if data['consent'] else 'No'}
"""
        try:
            # Send plain text to admissions
            msg_admissions = EmailMultiAlternatives(
                subject=subject_admissions,
                body=details_txt,
                from_email="info@sysfotech.uk",
                to=[admissions_email]
            )
            msg_admissions.send()
        except Exception as e:
            # Log error
            print(f"Error sending admissions email: {str(e)}")
            return Response({
                'error': 'Failed to send registration inquiry',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 2. Send professional HTML thank you email to student
        student_email = data['email']
        subject_student = "Thank you for registering with Sysfotech IT Services"
        
        # HTML Content in professional design matching their corporate white-orange theme
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Registration Confirmation</title>
</head>
<body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 40px 0;">
    <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <!-- Header -->
        <tr>
            <td bgcolor="#0f172a" style="padding: 40px 40px 30px 40px; text-align: center;">
                <h1 style="color: #ffffff; font-size: 24px; font-weight: 800; margin: 0; letter-spacing: -0.5px;">SYSFOTECH</h1>
                <p style="color: #f97316; font-size: 11px; font-weight: 700; text-transform: uppercase; margin: 5px 0 0 0; letter-spacing: 2px;">IT Services</p>
            </td>
        </tr>
        <!-- Hero section -->
        <tr>
            <td style="padding: 40px 40px 20px 40px;">
                <h2 style="color: #0f172a; font-size: 22px; font-weight: 700; margin-top: 0;">Hi {data['fullName']},</h2>
                <p style="color: #475569; font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
                    Thank you for registering for our training courses at Sysfotech! We have received your enrollment inquiry, and our admissions team is already reviewing your details.
                </p>
                <p style="color: #475569; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Here is a quick summary of your registration preferences:
                </p>
                <!-- Summary Card -->
                <table width="100%" cellpadding="12" cellspacing="0" style="background-color: #f8fafc; border-radius: 12px; border: 1px solid #edf2f7; margin-bottom: 30px;">
                    <tr>
                        <td width="35%" style="font-weight: 600; color: #64748b; font-size: 14px; border-bottom: 1px solid #edf2f7;">Selected Course(s)</td>
                        <td style="color: #0f172a; font-size: 14px; font-weight: 600; border-bottom: 1px solid #edf2f7;">{', '.join(data['selectedCourses'])}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: 600; color: #64748b; font-size: 14px; border-bottom: 1px solid #edf2f7;">Learning Mode</td>
                        <td style="color: #0f172a; font-size: 14px; border-bottom: 1px solid #edf2f7;">{data.get('learningMode') or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: 600; color: #64748b; font-size: 14px; border-bottom: 1px solid #edf2f7;">Duration</td>
                        <td style="color: #0f172a; font-size: 14px; border-bottom: 1px solid #edf2f7;">{data.get('courseDuration') or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: 600; color: #64748b; font-size: 14px;">Demo Registration</td>
                        <td style="color: #0f172a; font-size: 14px;">{data.get('wantDemo') or 'N/A'} (Batch: {data.get('demoBatch') or 'N/A'})</td>
                    </tr>
                </table>
            </td>
        </tr>
        <!-- Call to Action -->
        <tr>
            <td style="padding: 0 40px 40px 40px; text-align: center;">
                <div style="background-color: #f97316; border-radius: 8px; display: inline-block;">
                    <a href="https://wa.me/447442193577" target="_blank" style="color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 700; padding: 14px 30px; display: inline-block;">
                        Speak with our Advisors on WhatsApp
                    </a>
                </div>
            </td>
        </tr>
        <!-- Next Steps -->
        <tr>
            <td style="padding: 0 40px 40px 40px; border-top: 1px solid #edf2f7;">
                <h3 style="color: #0f172a; font-size: 16px; font-weight: 700; margin-top: 30px; margin-bottom: 10px;">What Happens Next?</h3>
                <ol style="color: #475569; font-size: 14px; line-height: 1.6; padding-left: 20px; margin-bottom: 0;">
                    <li style="margin-bottom: 8px;">Admissions Review: An advisor will verify your information.</li>
                    <li style="margin-bottom: 8px;">Schedule Alignment: We will reach out to schedule your demo class or confirm classroom timetables.</li>
                    <li>Syllabus Pack: We will send you the detailed module pack and pre-reading links.</li>
                </ol>
            </td>
        </tr>
        <!-- Footer -->
        <tr>
            <td bgcolor="#f1f5f9" style="padding: 30px; text-align: center; border-radius: 0 0 16px 16px;">
                <p style="color: #64748b; font-size: 12px; margin: 0;">Sysfotech IT Services Ltd. • London, UK</p>
                <p style="color: #94a3b8; font-size: 11px; margin: 5px 0 0 0;">This is an automated enrollment notification. Please do not reply directly to this message.</p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        text_content = strip_tags(html_content)

        try:
            msg_student = EmailMultiAlternatives(
                subject=subject_student,
                body=text_content,
                from_email="Sysfotech IT Services <info@sysfotech.uk>",
                to=[student_email]
            )
            msg_student.attach_alternative(html_content, "text/html")
            msg_student.send()
        except Exception as e:
            # Note: We still return 201 because the admissions email sent, but we log the student email error
            print(f"Error sending student confirmation email: {str(e)}")

        return Response({
            'message': 'Course registration submitted successfully! Admissions will contact you soon.'
        }, status=status.HTTP_201_CREATED)

class CouponValidateView(APIView):
    permission_classes = []

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Coupon code is required'}, status=status.HTTP_400_BAD_REQUEST)

        coupon = Coupon.objects.filter(code=code, is_active=True).first()
        if not coupon:
            return Response({'error': 'Invalid or inactive coupon code'}, status=status.HTTP_400_BAD_REQUEST)

        if coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
            return Response({'error': 'Coupon usage limit has been reached'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'code': coupon.code,
            'discount_percentage': coupon.discount_percentage,
            'message': 'Coupon applied successfully'
        })

class CreateStripePaymentIntentView(APIView):
    permission_classes = [] # Public access for guest checkout

    def post(self, request):
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            data = request.data
            
            email = data.get('email')
            name = data.get('name')
            phone = data.get('phone')
            course_slug = data.get('course_slug')
            course_title = data.get('course_title', 'Mock Course')
            coupon_code = data.get('coupon_code')
            payment_plan = data.get('payment_plan', 'full')
            
            # Fetch course to get real price (to prevent tampering)
            course = Course.objects.filter(slug=course_slug).first()
            if not course:
                # Use a default price for testing if course not found in db yet
                price = 351.00 if payment_plan == 'full' else 195.00
                course, _ = Course.objects.get_or_create(
                    slug=course_slug or 'selected-course',
                    defaults={
                        'title': course_title, 
                        'price': 429.00,
                        'one_time_price': 351.00,
                        'installment_admission_fee': 195.00
                    }
                )
            else:
                if payment_plan == 'installment' and course.installment_admission_fee:
                    price = float(course.installment_admission_fee)
                elif course.one_time_price:
                    price = float(course.one_time_price)
                else:
                    price = float(course.price)
                
            if coupon_code:
                coupon = Coupon.objects.filter(code=coupon_code, is_active=True).first()
                if coupon and (coupon.max_uses is None or coupon.uses_count < coupon.max_uses):
                    discount = float(price) * (float(coupon.discount_percentage) / 100.0)
                    price = float(price) - discount
                    # Increment use count for simplicity
                    coupon.uses_count += 1
                    coupon.save()

            amount = int(price * 100) # Stripe expects cents

            # Auth token check
            token = request.headers.get('Authorization')
            student = None
            if token:
                token = token.replace('Bearer ', '')
                student = Student.objects.filter(magic_link_token=token).first()
            
            # Check for existing student and reject if not authenticated as them
            existing_student = Student.objects.filter(email=email).first()
            if existing_student:
                if not student or student.email != email:
                    return Response(
                        {'error': 'This email is already registered. Please use a different email or access your existing courses from the Access Courses page.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                student = existing_student
                
                # Check if already enrolled in this course
                if Enrollment.objects.filter(student=student, course=course, status='paid').exists():
                    return Response(
                        {'error': 'You are already enrolled in this course.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Create PaymentIntent
            intent_kwargs = {
                'amount': amount,
                'currency': 'gbp',
                'payment_method_types': ['card'],
                'metadata': {
                    'student_name': name,
                    'student_email': email,
                    'student_phone': phone or 'N/A',
                    'course_title': course_title,
                    'payment_plan': payment_plan,
                }
            }
            if payment_plan == 'installment':
                customer_id = None
                if student and student.stripe_customer_id:
                    customer_id = student.stripe_customer_id
                else:
                    customer = stripe.Customer.create(email=email, name=name)
                    customer_id = customer.id
                    if student:
                        student.stripe_customer_id = customer.id
                        student.save()
                
                intent_kwargs['customer'] = customer_id
                intent_kwargs['setup_future_usage'] = 'off_session'
            
            intent = stripe.PaymentIntent.create(**intent_kwargs)
            
            # Create CheckoutSession
            session = CheckoutSession.objects.create(
                name=name,
                email=email,
                phone=phone,
                course=course,
                amount=price,
                payment_provider='stripe',
                payment_plan=payment_plan,
                payment_id=intent.id,
                status='pending'
            )

            # If user already logged in, they can keep using their existing token
            magic_link_token = str(student.magic_link_token) if student else str(session.magic_link_token)

            return Response({
                'clientSecret': intent.client_secret,
                'paymentIntentId': intent.id,
                'magicLinkToken': magic_link_token
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CreatePayPalOrderView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            data = request.data
            email = data.get('email')
            name = data.get('name')
            phone = data.get('phone')
            course_slug = data.get('course_slug')
            course_title = data.get('course_title', 'Mock Course')
            coupon_code = data.get('coupon_code')
            payment_plan = data.get('payment_plan', 'full')
            
            course = Course.objects.filter(slug=course_slug).first()
            if not course:
                price = 351.00 if payment_plan == 'full' else 195.00
                course, _ = Course.objects.get_or_create(
                    slug=course_slug or 'selected-course',
                    defaults={
                        'title': course_title, 
                        'price': 429.00,
                        'one_time_price': 351.00,
                        'installment_admission_fee': 195.00
                    }
                )
            else:
                if payment_plan == 'installment' and course.installment_admission_fee:
                    price = float(course.installment_admission_fee)
                elif course.one_time_price:
                    price = float(course.one_time_price)
                else:
                    price = float(course.price)

            if coupon_code:
                coupon = Coupon.objects.filter(code=coupon_code, is_active=True).first()
                if coupon and (coupon.max_uses is None or coupon.uses_count < coupon.max_uses):
                    discount = float(price) * (float(coupon.discount_percentage) / 100.0)
                    price = float(price) - discount
                    # Increment use count for simplicity
                    coupon.uses_count += 1
                    coupon.save()

            # Auth token check
            token = request.headers.get('Authorization')
            student = None
            if token:
                token = token.replace('Bearer ', '')
                student = Student.objects.filter(magic_link_token=token).first()
            
            # Check for existing student and reject if not authenticated as them
            existing_student = Student.objects.filter(email=email).first()
            if existing_student:
                if not student or student.email != email:
                    return Response(
                        {'error': 'This email is already registered. Please use a different email or access your existing courses from the Access Courses page.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                student = existing_student
                
                # Check if already enrolled in this course
                if Enrollment.objects.filter(student=student, course=course, status='paid').exists():
                    return Response(
                        {'error': 'You are already enrolled in this course.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Generate a fake order ID for demonstration
            import uuid
            fake_order_id = f"PAYPAL_ORDER_{uuid.uuid4().hex[:8]}"
            
            session = CheckoutSession.objects.create(
                name=name,
                email=email,
                phone=phone,
                course=course,
                amount=price,
                payment_provider='paypal',
                payment_plan=payment_plan,
                payment_id=fake_order_id,
                status='pending'
            )

            magic_link_token = str(student.magic_link_token) if student else str(session.magic_link_token)

            return Response({
                'orderID': fake_order_id,
                'magicLinkToken': magic_link_token
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

import json
from datetime import timedelta
from django.utils import timezone
from .models import PaymentInstallment

def create_enrollment_and_installments(session, payment_id, provider):
    student = Student.objects.filter(email=session.email).first()
    if not student:
        student = Student.objects.create(
            name=session.name,
            email=session.email,
            phone_number=session.phone,
            magic_link_token=session.magic_link_token
        )
    
    course = session.course
    # Calculate amounts
    if session.payment_plan == 'installment':
        # E.g. total 429, paid 195, remaining 234
        total_amount = float(course.price) if course else 429.00
        amount_paid = float(session.amount)
        amount_remaining = total_amount - amount_paid
    else:
        # Full payment
        total_amount = float(session.amount)
        amount_paid = float(session.amount)
        amount_remaining = 0.00
    
    enrollment = Enrollment.objects.create(
        student=student,
        course=course,
        amount=session.amount,
        total_amount=total_amount,
        amount_paid=amount_paid,
        amount_remaining=amount_remaining,
        payment_provider=provider,
        payment_plan=session.payment_plan,
        payment_id=payment_id,
        status='paid'
    )
    
    # Create installments
    today = timezone.now().date()
    if session.payment_plan == 'installment':
        # Admission Fee
        PaymentInstallment.objects.create(
            enrollment=enrollment,
            installment_number=1,
            name="Admission Fee",
            amount=amount_paid,
            due_date=today,
            status='paid',
            payment_id=payment_id
        )
        # Installment 1
        inst_amount = amount_remaining / 2
        PaymentInstallment.objects.create(
            enrollment=enrollment,
            installment_number=2,
            name="Installment 1",
            amount=inst_amount,
            due_date=today + timedelta(days=30),
            status='pending'
        )
        # Installment 2
        PaymentInstallment.objects.create(
            enrollment=enrollment,
            installment_number=3,
            name="Installment 2",
            amount=inst_amount,
            due_date=today + timedelta(days=60),
            status='pending'
        )
    else:
        # Full payment
        PaymentInstallment.objects.create(
            enrollment=enrollment,
            installment_number=1,
            name="Full Payment",
            amount=amount_paid,
            due_date=today,
            status='paid',
            payment_id=payment_id
        )
    
    try:
        send_invoice_email(enrollment)
    except Exception as e:
        print(f'Error sending invoice email: {e}')
    
    return enrollment

import logging
logger = logging.getLogger('sysfotech.webhook')

class StripeWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        
        try:
            if endpoint_secret and sig_header:
                event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            else:
                event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except Exception as e:
            logger.error(f'Webhook signature verification failed: {e}')
            return HttpResponse(status=400)

        logger.warning(f'[WEBHOOK] Received event: {event.type} | ID: {event.id}')

        # Handle the event
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            payment_id = payment_intent.id
            
            # Normal checkout session payment
            session = CheckoutSession.objects.filter(payment_id=payment_id).first()
            if session and session.status != 'completed':
                session.status = 'completed'
                session.save()
                
                enrollment = create_enrollment_and_installments(session, payment_id, 'stripe')
                
                # Create Stripe Subscription for installment plans
                import os
                price_id = enrollment.course.stripe_installment_price_id or os.getenv('STRIPE_INSTALLMENT_PRICE_ID')
                if enrollment.payment_plan == 'installment' and not enrollment.stripe_subscription_id and price_id:
                    student = enrollment.student
                    
                    # Ensure student has stripe_customer_id from the payment intent
                    customer_id = getattr(payment_intent, 'customer', None)
                    if not student.stripe_customer_id and customer_id:
                        student.stripe_customer_id = customer_id
                        student.save()

                    if student.stripe_customer_id:
                        try:
                            # Calculate exact date next month
                            now = timezone.now()
                            month = now.month + 1
                            year = now.year
                            if month > 12:
                                month = 1
                                year += 1
                            import calendar
                            max_day = calendar.monthrange(year, month)[1]
                            day = min(now.day, max_day)
                            next_month = now.replace(year=year, month=month, day=day, hour=12, minute=0, second=0)
                            
                            # Retrieve the payment method attached to the intent
                            intent_obj = stripe.PaymentIntent.retrieve(payment_id)
                            pm_id = intent_obj.payment_method
                            
                            if pm_id:
                                try:
                                    stripe.PaymentMethod.attach(pm_id, customer=student.stripe_customer_id)
                                except stripe.error.InvalidRequestError:
                                    # Payment method may already be attached to the customer, which is fine
                                    pass
                                stripe.Customer.modify(student.stripe_customer_id, invoice_settings={'default_payment_method': pm_id})
                            
                            subscription = stripe.Subscription.create(
                                customer=student.stripe_customer_id,
                                items=[{'price': price_id}],
                                default_payment_method=pm_id,
                                trial_end=int(next_month.timestamp()),
                                metadata={
                                    'enrollment_id': enrollment.id,
                                    'student_name': student.name,
                                    'student_email': student.email,
                                    'course_title': enrollment.course.title,
                                    'payment_plan': enrollment.payment_plan,
                                }
                            )
                            enrollment.stripe_subscription_id = subscription.id
                            enrollment.save()
                        except Exception as e:
                            print(f"Error creating Stripe subscription: {e}")
                
                

        elif event.type == 'invoice.paid':
            invoice = event.data.object
            logger.warning(f'[WEBHOOK] invoice.paid | amount_paid: {invoice.get("amount_paid", 0)} | subscription: {invoice.get("subscription")}')
            
            # Ignore $0 invoices (e.g. from free trial start)
            if invoice.get('amount_paid', 0) == 0:
                logger.warning('[WEBHOOK] Ignoring $0 invoice')
                return Response({'status': 'ignored'})

            subscription_id = invoice.get('subscription')
            if subscription_id:
                enrollment = Enrollment.objects.filter(stripe_subscription_id=subscription_id).first()
                logger.warning(f'[WEBHOOK] Enrollment lookup for sub {subscription_id}: {enrollment}')
                if enrollment:
                    installment = PaymentInstallment.objects.filter(enrollment=enrollment, status='pending').order_by('installment_number').first()
                    logger.warning(f'[WEBHOOK] Next pending installment: {installment}')
                    if installment:
                        installment.status = 'paid'
                        installment.payment_id = invoice.get('payment_intent')
                        installment.stripe_invoice_id = invoice.id
                        installment.stripe_payment_intent_id = invoice.get('payment_intent')
                        installment.save()
                        
                        enrollment.amount_paid += installment.amount
                        enrollment.amount_remaining -= installment.amount
                        if enrollment.amount_remaining < 0:
                            enrollment.amount_remaining = 0
                        enrollment.save()
                        logger.warning(f'[WEBHOOK] Installment {installment.name} marked PAID for {enrollment.student.name}')
                        
                        try:
                            send_installment_receipt_email(installment)
                            logger.warning(f'[WEBHOOK] Installment receipt email sent to {enrollment.student.email}')
                        except Exception as e:
                            logger.error(f'Error sending installment receipt: {e}')
                        
                        if not PaymentInstallment.objects.filter(enrollment=enrollment, status='pending').exists():
                            try:
                                stripe.Subscription.delete(subscription_id)
                                logger.warning(f'[WEBHOOK] All installments paid. Subscription {subscription_id} cancelled.')
                            except Exception as e:
                                logger.error(f'Error canceling subscription: {e}')
                else:
                    logger.error(f'[WEBHOOK] No enrollment found for subscription_id: {subscription_id}')
            else:
                logger.warning('[WEBHOOK] invoice.paid event has no subscription_id')

        elif event.type == 'invoice.payment_failed':
            invoice = event.data.object
            subscription_id = invoice.get('subscription')
            logger.warning(f'[WEBHOOK] invoice.payment_failed | subscription: {subscription_id}')
            if subscription_id:
                enrollment = Enrollment.objects.filter(stripe_subscription_id=subscription_id).first()
                if enrollment:
                    installment = PaymentInstallment.objects.filter(enrollment=enrollment, status='pending').order_by('installment_number').first()
                    if installment:
                        installment.status = 'failed'
                        installment.save()
                        logger.warning(f'[WEBHOOK] Installment {installment.name} marked FAILED for {enrollment.student.name}')
                        
                        try:
                            send_installment_failed_email(installment)
                            logger.warning(f'[WEBHOOK] Installment failed email sent to {enrollment.student.email}')
                        except Exception as e:
                            logger.error(f'Error sending installment failed email: {e}')

        return HttpResponse(status=200)

class PayPalCaptureView(APIView):
    permission_classes = []

    def post(self, request):
        order_id = request.data.get('orderID')
        session = CheckoutSession.objects.filter(payment_id=order_id).first()
        if session:
            if session.status != 'completed':
                session.status = 'completed'
                session.save()
                
                enrollment = create_enrollment_and_installments(session, order_id, 'paypal')
                
                
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

class TestCaptureView(APIView):
    permission_classes = []

    def post(self, request):
        import stripe
        import os
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        payment_id = request.data.get('payment_id')
        session = CheckoutSession.objects.filter(payment_id=payment_id).first()
        if session:
            if session.status != 'completed':
                session.status = 'completed'
                session.save()
                
                enrollment = create_enrollment_and_installments(session, payment_id, session.payment_provider)
                
                if session.payment_provider == 'stripe' and enrollment.payment_plan == 'installment' and not enrollment.stripe_subscription_id:
                    import os
                    price_id = enrollment.course.stripe_installment_price_id or os.getenv('STRIPE_INSTALLMENT_PRICE_ID')
                    if price_id:
                        student = enrollment.student
                        try:
                            intent_obj = stripe.PaymentIntent.retrieve(payment_id)
                            customer_id = getattr(intent_obj, 'customer', None)
                            if not student.stripe_customer_id and customer_id:
                                student.stripe_customer_id = customer_id
                                student.save()

                            if student.stripe_customer_id:
                                from django.utils import timezone
                                now = timezone.now()
                                month = now.month + 1
                                year = now.year
                                if month > 12:
                                    month = 1
                                    year += 1
                                import calendar
                                max_day = calendar.monthrange(year, month)[1]
                                day = min(now.day, max_day)
                                next_month = now.replace(year=year, month=month, day=day, hour=12, minute=0, second=0)
                                
                                pm_id = intent_obj.payment_method
                                if pm_id:
                                    try:
                                        stripe.PaymentMethod.attach(pm_id, customer=student.stripe_customer_id)
                                    except stripe.error.InvalidRequestError:
                                        # Payment method may already be attached to the customer, which is fine
                                        pass
                                    stripe.Customer.modify(student.stripe_customer_id, invoice_settings={'default_payment_method': pm_id})
                                
                                subscription = stripe.Subscription.create(
                                    customer=student.stripe_customer_id,
                                    items=[{'price': price_id}],
                                    default_payment_method=pm_id,
                                    trial_end=int(next_month.timestamp()),
                                    metadata={
                                        'enrollment_id': enrollment.id,
                                        'student_name': student.name,
                                        'student_email': student.email,
                                        'course_title': enrollment.course.title,
                                        'payment_plan': enrollment.payment_plan,
                                    }
                                )
                                enrollment.stripe_subscription_id = subscription.id
                                enrollment.save()
                        except Exception as e:
                            print(f"Error creating subscription in TestCaptureView: {e}")
                
                
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

class TestInstallmentCaptureView(APIView):
    permission_classes = []

    def post(self, request):
        payment_id = request.data.get('payment_id')
        installment_id = request.data.get('installment_id')
        
        installment = PaymentInstallment.objects.filter(id=installment_id).first()
        if installment and installment.status != 'paid':
            installment.status = 'paid'
            installment.payment_id = payment_id
            installment.save()
            
            enrollment = installment.enrollment
            enrollment.amount_paid += installment.amount
            enrollment.amount_remaining -= installment.amount
            if enrollment.amount_remaining < 0:
                enrollment.amount_remaining = 0
            enrollment.save()
            
            from .models import Transaction
            Transaction.objects.create(
                student=enrollment.student,
                course=enrollment.course,
                amount=installment.amount,
                payment_method='stripe',
                status='succeeded',
                payment_id=payment_id
            )
            
            # Send payment success email
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@sysfotech.uk')
                student = enrollment.student
                send_mail(
                    subject=f'Payment Receipt for {installment.name}',
                    message=f'Hello {student.name},\n\nWe have successfully received your payment of £{installment.amount} for {installment.name} ({enrollment.course.title}).\n\nThank you for your payment.\n\nSysfotech IT Services',
                    from_email=from_email,
                    recipient_list=[student.email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Failed to send installment receipt: {e}")
                
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        redirect_path = request.data.get('redirect', '')
        
        if not email:
            return Response({'error': 'Email is required'}, status=400)
            
        student = Student.objects.filter(email=email).first()
        if student:
            magic_link_url = f"{settings.FRONTEND_URL}/verify?token={student.magic_link_token}"
            if redirect_path:
                magic_link_url += f"&redirect={redirect_path}"
                
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
            
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject='Your Course Access Link - Sysfotech',
                    message=f'Hello {student.name},\n\nClick the link below to securely access your student dashboard:\n{magic_link_url}\n\nThank you for choosing Sysfotech!',
                    from_email=from_email,
                    recipient_list=[student.email],
                    fail_silently=False,
                )
                return Response({'message': 'We have sent a secure access link to your email!'})
            except Exception as e:
                return Response({'error': 'Failed to send access link email. Please try again.'}, status=500)
            
        return Response({'error': 'No account found with this email.'}, status=404)
class StudentEnrollmentsView(APIView):
    permission_classes = []

    def get(self, request):
        token = request.headers.get('Authorization')
        if not token:
            return Response({'error': 'Unauthorized'}, status=401)
            
        token = token.replace('Bearer ', '')
        student = Student.objects.filter(magic_link_token=token).first()
        
        if not student:
            return Response({'error': 'Invalid token'}, status=401)
            
        enrollments = Enrollment.objects.filter(student=student, status='paid')
        
        data = []
        for e in enrollments:
            installments_data = []
            if e.payment_plan == 'installment':
                for inst in e.installments.all().order_by('installment_number'):
                    installments_data.append({
                        'id': str(inst.id),
                        'name': inst.name,
                        'amount': str(inst.amount),
                        'due_date': inst.due_date.isoformat(),
                        'status': inst.status
                    })
            
            data.append({
                'id': e.id,
                'course': {
                    'title': e.course.title,
                    'slug': e.course.slug,
                    'image': e.course.image_url,
                },
                'amount': str(e.total_amount),
                'amount_paid': str(e.amount_paid),
                'amount_remaining': str(e.amount_remaining),
                'date': e.created_at.strftime("%b %d, %Y"),
                'status': e.status,
                'payment_plan': e.payment_plan,
                'installments': installments_data
            })
            
        return Response({
            'enrollments': data, 
            'student': {'name': student.name, 'email': student.email}
        })


class InvoiceDownloadView(APIView):
    """Download a PDF invoice for a specific enrollment."""
    permission_classes = []

    def get(self, request, enrollment_id):
        token = request.headers.get('Authorization')
        if not token:
            return Response({'error': 'Unauthorized'}, status=401)

        token = token.replace('Bearer ', '')
        student = Student.objects.filter(magic_link_token=token).first()

        if not student:
            return Response({'error': 'Invalid token'}, status=401)

        enrollment = Enrollment.objects.filter(
            id=enrollment_id, student=student, status='paid'
        ).first()

        if not enrollment:
            return Response({'error': 'Invoice not found'}, status=404)

        pdf_bytes = generate_invoice_pdf(enrollment)
        inv_number = f'INV-{enrollment.id:05d}'

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{inv_number}.pdf"'
        return response

# ─── React Admin APIs ───────────────────────────────────────────────
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAdminUser, AllowAny
from .serializers import (
    StudentSerializer, CourseSerializer, CheckoutSessionSerializer,
    CouponSerializer, EnrollmentSerializer, TransactionSerializer
)

class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        
        if user and user.is_superuser:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'token': token.key, 'username': user.username})
        return Response({'error': 'Invalid credentials or not an admin'}, status=status.HTTP_401_UNAUTHORIZED)

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by('-created_at')
    serializer_class = StudentSerializer
    permission_classes = [IsAdminUser]

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().order_by('-created_at')
    serializer_class = CourseSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_slug']:
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='slug/(?P<slug>[^/.]+)')
    def by_slug(self, request, slug=None):
        course = get_object_or_404(Course, slug=slug)
        serializer = self.get_serializer(course)
        return Response(serializer.data)

class CheckoutSessionViewSet(viewsets.ModelViewSet):
    queryset = CheckoutSession.objects.all().order_by('-created_at')
    serializer_class = CheckoutSessionSerializer
    permission_classes = [IsAdminUser]

class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all().order_by('-created_at')
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]

class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.all().select_related('student', 'course').order_by('-created_at')
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAdminUser]

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().order_by('-created_at')
    serializer_class = TransactionSerializer
    permission_classes = [IsAdminUser]

from .models import PaymentInstallment
from .serializers import PaymentInstallmentSerializer

class InstallmentDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        installment = PaymentInstallment.objects.filter(id=pk).first()
        if not installment:
            return Response({'error': 'Installment not found or invalid link'}, status=404)
        
        return Response({
            'id': installment.id,
            'name': installment.name,
            'amount': installment.amount,
            'status': installment.status,
            'due_date': installment.due_date,
            'course_title': installment.enrollment.course.title,
            'student_name': installment.enrollment.student.name,
            'student_email': installment.enrollment.student.email
        })

class InstallmentPayView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        installment = PaymentInstallment.objects.filter(id=pk).first()
        if not installment:
            return Response({'error': 'Installment not found'}, status=404)
            
        if installment.status == 'paid':
            return Response({'error': 'This installment has already been paid'}, status=400)
            
        provider = request.data.get('provider', 'stripe')
        
        try:
            if provider == 'stripe':
                stripe.api_key = settings.STRIPE_SECRET_KEY
                student = installment.enrollment.student
                intent = stripe.PaymentIntent.create(
                    amount=int(installment.amount * 100),
                    currency='gbp',
                    description=f"Installment: {installment.name} for {installment.enrollment.course.title}",
                    metadata={
                        'installment_id': str(installment.id),
                        'enrollment_id': installment.enrollment.id,
                        'type': 'installment_payment',
                        'student_name': student.name,
                        'student_email': student.email,
                        'student_phone': student.phone_number or 'N/A'
                    }
                )
                return Response({'clientSecret': intent.client_secret, 'amount': installment.amount})
            else:
                return Response({'error': 'Provider not supported yet'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
class PaymentInstallmentViewSet(viewsets.ModelViewSet):
    queryset = PaymentInstallment.objects.all().select_related('enrollment__student', 'enrollment__course').order_by('due_date')
    serializer_class = PaymentInstallmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'enrollment__payment_plan']
    search_fields = ['enrollment__student__name', 'enrollment__student__email', 'name', 'payment_id']
    ordering_fields = ['due_date', 'created_at', 'amount']

class SendInstallmentLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            installment = PaymentInstallment.objects.select_related('enrollment__student', 'enrollment__course').get(id=pk)
            
            if installment.status == 'paid':
                return Response({'error': 'This installment is already paid.'}, status=400)

            student = installment.enrollment.student
            course = installment.enrollment.course
            link = f"{settings.FRONTEND_URL}/pay-installment/{installment.id}"
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
            
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=f'Action Required: Payment Due for {course.title}',
                    message=(
                        f'Hello {student.name},\n\n'
                        f'This is a friendly reminder that your payment for "{installment.name}" is due on {installment.due_date.strftime("%B %d, %Y")}.\n\n'
                        f'Amount Due: £{installment.amount}\n\n'
                        f'Please use the secure link below to complete your payment:\n{link}\n\n'
                        f'Thank you,\nSysfotech IT Services'
                    ),
                    from_email=from_email,
                    recipient_list=[student.email],
                    fail_silently=False,
                )
                return Response({'message': 'Payment link sent successfully.'})
            except Exception as e:
                return Response({'error': 'Failed to send email. Please try again later.'}, status=500)
                
        except PaymentInstallment.DoesNotExist:
            return Response({'error': 'Installment not found'}, status=404)
