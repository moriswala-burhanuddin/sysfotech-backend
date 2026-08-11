from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'contact-info', views.ContactInfoViewSet)
router.register(r'inquiries', views.InquiryViewSet)

# The API URLs are now determined automatically by the router
urlpatterns = [
    # Course Registrations API
    path('course-registrations/', views.CourseRegistrationView.as_view(), name='course-registrations'),
    path('create-payment-intent/', views.CreateStripePaymentIntentView.as_view(), name='create-payment-intent'),
    path('create-paypal-order/', views.CreatePayPalOrderView.as_view(), name='create-paypal-order'),
    path('webhooks/stripe/', views.StripeWebhookView.as_view(), name='stripe-webhook'),
    path('paypal/capture/', views.PayPalCaptureView.as_view(), name='paypal-capture'),
    path('test/capture/', views.TestCaptureView.as_view(), name='test-capture'),
    path('student/enrollments/', views.StudentEnrollmentsView.as_view(), name='student-enrollments'),
    # Router URLs (API endpoints)
    path('', include(router.urls)),
]
