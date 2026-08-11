from rest_framework import serializers
from .models import ContactInfo, Inquiry
import re

class ContactInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInfo
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class InquirySerializer(serializers.ModelSerializer):
    def validate_phone_number(self, value):
        """Custom validation for phone number"""
        if not value or value.strip() == "" or value == "+00000000000":
            return None
        
        # Clean the phone number by removing spaces and formatting
        if value:
            cleaned = re.sub(r'[^\d\+]', '', value)
            # Ensure it starts with + if it was there originally
            if value.startswith('+') and not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            return cleaned
        
        return value
    
    def validate(self, data):
        """Custom validation for the entire serializer"""
        # Clean up phone number if it's empty or the fallback value
        if 'phone_number' in data and (not data['phone_number'] or data['phone_number'] == "+00000000000"):
            data['phone_number'] = None
        elif 'phone_number' in data and data['phone_number']:
            # Clean the phone number
            cleaned = re.sub(r'[^\d\+]', '', data['phone_number'])
            if data['phone_number'].startswith('+') and not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            data['phone_number'] = cleaned
        
        return data

    class Meta:
        model = Inquiry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'contacted_at']

class ContactInfoPublicSerializer(serializers.ModelSerializer):
    """Public serializer for contact info (excludes internal fields)"""
    class Meta:
        model = ContactInfo
        fields = ['company_name', 'address', 'phone_number', 'email', 'slogan', 'website', 'facebook', 'twitter', 'linkedin', 'instagram', 'working_hours']

class CourseRegistrationSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=255)
    dateOfBirth = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=50)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    postcode = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    currentStatus = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    companyName = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    jobRole = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    selectedCourses = serializers.ListField(child=serializers.CharField(), min_length=1)
    learningMode = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    courseDuration = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    experienceLevel = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    reasons = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    hearAboutUs = serializers.ListField(child=serializers.CharField(), required=False, default=[])
    wantDemo = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)
    demoBatch = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    demoTime = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    consent = serializers.BooleanField()

