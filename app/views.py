from django.shortcuts import render
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
    magic_link_url = f'http://localhost:8080/verify?token={enrollment.student.magic_link_token}'

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
            
            # Fetch course to get real price (to prevent tampering)
            course = Course.objects.filter(slug=course_slug).first()
            if not course:
                # Use a default price for testing if course not found in db yet
                price = 99.99
                course, _ = Course.objects.get_or_create(
                    slug=course_slug or 'selected-course',
                    defaults={'title': course_title, 'price': price}
                )
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
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='gbp',
                payment_method_types=['card'],
                metadata={'student_email': email, 'course_slug': course_slug}
            )
            
            # Create CheckoutSession
            session = CheckoutSession.objects.create(
                name=name,
                email=email,
                phone=phone,
                course=course,
                amount=price,
                payment_provider='stripe',
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
            
            course = Course.objects.filter(slug=course_slug).first()
            if not course:
                price = 99.99
                course, _ = Course.objects.get_or_create(
                    slug=course_slug or 'selected-course',
                    defaults={'title': course_title, 'price': price}
                )
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

class StripeWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        payload = request.body
        
        try:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except Exception as e:
            return HttpResponse(status=400)

        # Handle the event
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            payment_id = payment_intent.id
            
            session = CheckoutSession.objects.filter(payment_id=payment_id).first()
            if session and session.status != 'completed':
                session.status = 'completed'
                session.save()
                
                student = Student.objects.filter(email=session.email).first()
                if not student:
                    student = Student.objects.create(
                        name=session.name,
                        email=session.email,
                        phone_number=session.phone,
                        magic_link_token=session.magic_link_token
                    )
                
                enrollment = Enrollment.objects.create(
                    student=student,
                    course=session.course,
                    amount=session.amount,
                    payment_provider='stripe',
                    payment_id=payment_id,
                    status='paid'
                )
                
                # Send PDF invoice email
                try:
                    send_invoice_email(enrollment)
                except Exception as e:
                    print(f'Error sending invoice email: {e}')

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
                
                student = Student.objects.filter(email=session.email).first()
                if not student:
                    student = Student.objects.create(
                        name=session.name,
                        email=session.email,
                        phone_number=session.phone,
                        magic_link_token=session.magic_link_token
                    )
                
                enrollment = Enrollment.objects.create(
                    student=student,
                    course=session.course,
                    amount=session.amount,
                    payment_provider='paypal',
                    payment_id=order_id,
                    status='paid'
                )
                
                try:
                    send_invoice_email(enrollment)
                except Exception as e:
                    print(f'Error sending invoice email: {e}')
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

class TestCaptureView(APIView):
    permission_classes = []

    def post(self, request):
        payment_id = request.data.get('payment_id')
        session = CheckoutSession.objects.filter(payment_id=payment_id).first()
        if session:
            if session.status != 'completed':
                session.status = 'completed'
                session.save()
                
                student = Student.objects.filter(email=session.email).first()
                if not student:
                    student = Student.objects.create(
                        name=session.name,
                        email=session.email,
                        phone_number=session.phone,
                        magic_link_token=session.magic_link_token
                    )
                
                enrollment = Enrollment.objects.create(
                    student=student,
                    course=session.course,
                    amount=session.amount,
                    payment_provider=session.payment_provider,
                    payment_id=payment_id,
                    status='paid'
                )
                
                try:
                    send_invoice_email(enrollment)
                except Exception as e:
                    print(f'Error sending invoice email: {e}')
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required'}, status=400)
            
        student = Student.objects.filter(email=email).first()
        if student:
            magic_link_url = f"http://localhost:8080/verify?token={student.magic_link_token}"
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
            data.append({
                'id': e.id,
                'course': {
                    'title': e.course.title,
                    'slug': e.course.slug,
                    'image': e.course.image_url,
                },
                'amount': str(e.amount),
                'date': e.created_at.strftime("%b %d, %Y"),
                'status': e.status
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
    permission_classes = [IsAdminUser]

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
