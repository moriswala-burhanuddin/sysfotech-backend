from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'contact-info', views.ContactInfoViewSet)
router.register(r'inquiries', views.InquiryViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'courses', views.CourseViewSet)
router.register(r'checkout-sessions', views.CheckoutSessionViewSet)
router.register(r'coupons', views.CouponViewSet)
router.register(r'enrollments', views.EnrollmentViewSet)
router.register(r'transactions', views.TransactionViewSet)

router.register(r'installments', views.PaymentInstallmentViewSet, basename='installment')

# The API URLs are now determined automatically by the router
urlpatterns = [
    # React Admin Login
    path('admin/login/', views.AdminLoginView.as_view(), name='admin-login'),
    
    # Course Registrations API
    path('coupons/validate/', views.CouponValidateView.as_view(), name='coupon-validate'),
    path('course-registrations/', views.CourseRegistrationView.as_view(), name='course-registrations'),
    path('create-payment-intent/', views.CreateStripePaymentIntentView.as_view(), name='create-payment-intent'),
    path('create-paypal-order/', views.CreatePayPalOrderView.as_view(), name='create-paypal-order'),
    path('webhooks/stripe/', views.StripeWebhookView.as_view(), name='stripe-webhook'),
    path('paypal/capture/', views.PayPalCaptureView.as_view(), name='paypal-capture'),
    path('test/capture/', views.TestCaptureView.as_view(), name='test-capture'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('student/enrollments/', views.StudentEnrollmentsView.as_view(), name='student-enrollments'),
    path('student/invoice/<int:enrollment_id>/', views.InvoiceDownloadView.as_view(), name='invoice-download'),
    # Router URLs (API endpoints)
    path('', include(router.urls)),
]
