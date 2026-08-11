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
from django.conf import settings
import stripe
from .models import Course, Student, Transaction, Enrollment

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
                
            amount = int(price * 100) # Stripe expects cents

            # Create or get student (smart guest checkout)
            student, created = Student.objects.get_or_create(
                email=email,
                defaults={'name': name, 'phone_number': phone}
            )
            
            # If student exists but phone is missing, update it
            if not created and phone and not student.phone_number:
                student.phone_number = phone
                student.save()

            # Create PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                payment_method_types=['card'],
                metadata={'student_email': email, 'course_slug': course_slug}
            )
            
            # Create enrollment record as pending
            Enrollment.objects.create(
                student=student,
                course=course,
                amount=price,
                payment_provider='stripe',
                payment_id=intent.id,
                status='pending'
            )

            return Response({
                'clientSecret': intent.client_secret,
                'paymentIntentId': intent.id,
                'magicLinkToken': str(student.magic_link_token) # For testing purposes only to show in walkthrough
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
            
            course = Course.objects.filter(slug=course_slug).first()
            if not course:
                price = 99.99
                course, _ = Course.objects.get_or_create(
                    slug=course_slug or 'selected-course',
                    defaults={'title': course_title, 'price': price}
                )
            else:
                price = float(course.price)

            # Create or get student
            student, created = Student.objects.get_or_create(
                email=email,
                defaults={'name': name, 'phone_number': phone}
            )
            
            # If student exists but phone is missing, update it
            if not created and phone and not student.phone_number:
                student.phone_number = phone
                student.save()
            
            # Since this is a simple mock endpoint without real PayPal SDK on backend:
            # Generate a fake order ID for demonstration
            import uuid
            fake_order_id = f"PAYPAL_ORDER_{uuid.uuid4().hex[:8]}"
            
            Enrollment.objects.create(
                student=student,
                course=course,
                amount=price,
                payment_provider='paypal',
                payment_id=fake_order_id,
                status='pending'
            )

            return Response({
                'orderID': fake_order_id,
                'magicLinkToken': str(student.magic_link_token)
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

import json
from django.core.mail import send_mail

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
            
            enrollment = Enrollment.objects.filter(payment_id=payment_id).first()
            if enrollment:
                enrollment.status = 'paid'
                enrollment.save()
                
                # Send email
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
                send_mail(
                    subject='Welcome to your Course! - Sysfotech',
                    message=f'Hello {enrollment.student.name},\n\nYou have successfully enrolled in {enrollment.course.title}.\n\nAccess your student dashboard here:\nhttp://localhost:8080/dashboard?token={enrollment.student.magic_link_token}\n\nThank you for choosing Sysfotech!',
                    from_email=from_email,
                    recipient_list=[enrollment.student.email],
                    fail_silently=False,
                )

        return HttpResponse(status=200)

class PayPalCaptureView(APIView):
    permission_classes = []

    def post(self, request):
        order_id = request.data.get('orderID')
        enrollment = Enrollment.objects.filter(payment_id=order_id).first()
        if enrollment:
            enrollment.status = 'paid'
            enrollment.save()
            
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
            send_mail(
                subject='Welcome to your Course! - Sysfotech',
                message=f'Hello {enrollment.student.name},\n\nYou have successfully enrolled in {enrollment.course.title}.\n\nAccess your student dashboard here:\nhttp://localhost:8080/dashboard?token={enrollment.student.magic_link_token}\n\nThank you for choosing Sysfotech!',
                from_email=from_email,
                recipient_list=[enrollment.student.email],
                fail_silently=False,
            )
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

class TestCaptureView(APIView):
    permission_classes = []

    def post(self, request):
        payment_id = request.data.get('payment_id')
        enrollment = Enrollment.objects.filter(payment_id=payment_id).first()
        if enrollment:
            if enrollment.status != 'paid':
                enrollment.status = 'paid'
                enrollment.save()
                
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sysfotech.uk')
                send_mail(
                    subject='Welcome to your Course! - Sysfotech',
                    message=f'Hello {enrollment.student.name},\n\nYou have successfully enrolled in {enrollment.course.title}.\n\nAccess your student dashboard here:\nhttp://localhost:8080/dashboard?token={enrollment.student.magic_link_token}\n\nThank you for choosing Sysfotech!',
                    from_email=from_email,
                    recipient_list=[enrollment.student.email],
                    fail_silently=False,
                )
            return Response({'status': 'success'})
        return Response({'status': 'failed'}, status=400)

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
