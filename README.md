# SYSFOTech - Simplified Django Backend

A simplified Django REST API backend for SYSFOTech with only essential models for contact information and customer inquiries.

## Features

- **Contact Information Management**: Store and manage company contact details
- **Customer Inquiry System**: Handle customer inquiries with status tracking
- **Django Admin Panel**: Full admin interface for managing data
- **REST API**: Clean API endpoints for frontend integration
- **React Frontend Support**: Serves React application for client-side routing

## Models

### ContactInfo
- Company name, address, phone, email
- Social media links (Facebook, Twitter, LinkedIn, Instagram)
- Working hours and website
- Active/inactive status

### Inquiry
- Customer details (name, email, phone)
- Project requirements and description
- Budget range and timeline
- Status tracking (New, Contacted, In Progress, Completed, Cancelled)
- Source tracking and internal notes

## API Endpoints

### Contact Info
- `GET /api/contact-info/` - List all contact info
- `GET /api/contact-info/{id}/` - Get specific contact info
- `POST /api/contact-info/` - Create new contact info (admin only)
- `PUT /api/contact-info/{id}/` - Update contact info (admin only)
- `DELETE /api/contact-info/{id}/` - Delete contact info (admin only)
- `GET /api/contact-info/public/` - Get public contact info

### Inquiries
- `GET /api/inquiries/` - List all inquiries (admin only)
- `GET /api/inquiries/{id}/` - Get specific inquiry (admin only)
- `POST /api/inquiries/` - Create new inquiry (public)
- `PUT /api/inquiries/{id}/` - Update inquiry (admin only)
- `DELETE /api/inquiries/{id}/` - Delete inquiry (admin only)
- `PATCH /api/inquiries/{id}/update_status/` - Update inquiry status (admin only)

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Create Superuser
```bash
python manage.py createsuperuser
```

### 4. Run Development Server
```bash
python manage.py runserver
```

### 5. Access Admin Panel
Visit `http://localhost:8000/admin/` and login with your superuser credentials.

## Admin Panel Features

### ContactInfo Admin
- List view with company name, email, phone, status
- Filter by active status and date
- Search by company name, email, phone, address
- Bulk actions for activating/deactivating records
- Organized fieldsets for easy data entry

### Inquiry Admin
- List view with customer name, email, service, status
- Filter by status, service, source, date
- Search by customer details and project description
- Bulk actions for status updates
- Inline editing for quick status changes

## File Structure

```
sysfotech/
├── app/
│   ├── models.py          # ContactInfo and Inquiry models
│   ├── serializers.py     # API serializers
│   ├── views.py          # API viewsets
│   ├── admin.py          # Admin panel configuration
│   └── urls.py           # API URL routing
├── sysfotech/
│   ├── settings.py       # Django settings
│   └── urls.py          # Main URL configuration
├── static/              # Static files for React app
├── templates/           # HTML templates
└── manage.py           # Django management script
```

## Environment Variables

The project uses the following key settings:
- `DEBUG = True` (for development)
- `ALLOWED_HOSTS = ['*']` (for development)
- Custom admin site branding
- CORS enabled for frontend integration

## Security Notes

- Admin panel requires authentication
- Inquiry creation is public (no authentication required)
- All other operations require admin authentication
- CORS is configured for development

## Next Steps

1. Add sample data through admin panel
2. Test API endpoints
3. Integrate with React frontend
4. Configure production settings
5. Set up proper CORS for production
