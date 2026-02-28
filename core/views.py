from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Apartment, Lease, UserProfile, Maintenance, Notification, RentPayment, RentDueDate, ApartmentPhoto
from datetime import datetime, timedelta
from django.db.models import Sum, Q, Count
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.http import HttpResponse
import csv
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
# PDF Export (optional)
try:
    from reportlab.lib.pagesizes import letter  # noqa
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer  # noqa
    from reportlab.lib import colors  # noqa
    from reportlab.lib.styles import getSampleStyleSheet  # noqa
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False
from .emails import (
    send_lease_confirmation_email, 
    send_payment_confirmation_email, 
    send_cancellation_email,
    send_admin_notification
)
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.utils.dateparse import parse_date
import calendar

# ============================================
# PUBLIC VIEWS (No login required)
# ============================================

def _normalized_photo_urls(raw_values):
    """Parse comma/newline-separated URL values into a clean list."""
    photo_urls = []
    for raw in raw_values:
        if not raw:
            continue
        for line in str(raw).replace('\r', '\n').split('\n'):
            for value in line.split(','):
                url = value.strip()
                if url:
                    photo_urls.append(url)
    return photo_urls


def _whole_months_between(start_date, end_date):
    """Return whole-month difference similar to relativedelta(...).years/months."""
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(months, 0)


def _add_months(date_obj, months=1):
    """Add months to a date, clamping to month end when needed."""
    month_index = (date_obj.month - 1) + months
    year = date_obj.year + month_index // 12
    month = (month_index % 12) + 1
    day = min(date_obj.day, calendar.monthrange(year, month)[1])
    return date_obj.replace(year=year, month=month, day=day)


def _last_day_of_month(date_obj):
    """Return the last date of the date's month."""
    return date_obj.replace(day=calendar.monthrange(date_obj.year, date_obj.month)[1])

def home(request):
    """Landing page - displays property info and call to action"""
    return render(request, 'home.html')

def user_login(request):
    """Handle tenant/admin login - authenticates user and redirects to dashboard"""
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect to 'next' parameter if exists, otherwise dashboard
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'login.html')

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST.get('email', '')
        contact_number = request.POST.get('contact_number', '')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'register.html')
        
        user = User.objects.create_user(username=username, password=password, email=email)
        
        # Create user profile with contact number
        UserProfile.objects.create(
            user=user,
            contact_number=contact_number
        )
        
        login(request, user)
        messages.success(request, 'Account created successfully!')
        return redirect('dashboard')
    
    return render(request, 'register.html')

# ============================================
# TENANT DASHBOARD & LEASE MANAGEMENT
# ============================================

@login_required
def dashboard(request):
    """Tenant dashboard - shows their leases, notifications, and due payments"""
    # Staff users should use the admin dashboard view.
    if request.user.is_staff:
        return redirect('admin_dashboard')

    leases = Lease.objects.filter(tenant=request.user).order_by('-created_at')
    unread_notifications_count = Notification.objects.filter(
        tenant=request.user,
        is_read=False
    ).count()
    due_payments_count = RentDueDate.objects.filter(
        lease__tenant=request.user,
        is_paid=False,
        due_date__lte=datetime.now().date()
    ).count()

    return render(request, 'dashboard.html', {
        # Existing keys
        'leases': leases,
        'unread_notifications_count': unread_notifications_count,
        'due_payments_count': due_payments_count,
        # Dashboard template keys (tenant branch)
        'is_admin': False,
        'bookings': leases,
        'bookings_pending': leases.filter(status='pending').count(),
        'bookings_active': leases.filter(status='active').count(),
    })

def apartments(request):
    """Public apartments listing - shows available apartments"""
    # simply display all currently available apartments; search/filter UI removed
    available_apartments = Apartment.objects.filter(is_available=True)
    
    context = {'apartments': available_apartments}

    # Use public template instead of dashboard template
    return render(request, 'apartments_list.html', context)
@login_required
def apartment_detail(request, apartment_id):
    """Display detailed apartment information for public viewing
    
    Shows:
    - Apartment details (unit number, type, rent price)
    - Description and amenities
    - Maximum occupants
    - Photos/images
    
    This is a public view (no login required) to allow browsing apartments
    """
    apartment = get_object_or_404(Apartment, id=apartment_id)
    return render(request, 'apartment_detail.html', {'apartment': apartment})

@login_required
def lease_apartment(request, apartment_id):
    """Tenant submits lease application for an apartment
    
    POST: Create lease with:
    - Move-in and move-out dates (validates date range)
    - Number of occupants (validates against max_occupants)
    - Special requests (additional notes)
    - Status set to 'pending' awaiting admin approval
    - Total price calculated: months * monthly_rent
    
    Validation checks:
    - Required fields present
    - Dates in correct format (YYYY-MM-DD)
    - Move-out after move-in
    - Move-in not in past
    - Dates don't conflict with existing leases (check_availability)
    - Occupants within limits
    
    On success:
    - Create Lease record with status='pending'
    - Create Notification for tenant
    - Send confirmation email to tenant
    - Notify admin of new lease application
    - Redirect to confirmation page
    
    GET: Display form with apartment details and occupied dates for calendar
    """
    apartment = get_object_or_404(Apartment, id=apartment_id)
    
    if request.method == 'POST':
        move_in = request.POST.get('move_in', '')
        move_out = request.POST.get('move_out', '')
        num_occupants = request.POST.get('num_occupants', '')
        special_requests = request.POST.get('special_requests', '')
        
        # Validate required fields
        if not move_in or not num_occupants:
            messages.error(request, 'Please fill in all required fields (Move-in date and Number of occupants)')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        try:
            num_occupants = int(num_occupants)
        except ValueError:
            messages.error(request, 'Number of occupants must be a valid number')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        # Convert to date objects
        try:
            move_in_date = datetime.strptime(move_in, '%Y-%m-%d').date()
            if move_out:
                move_out_date = datetime.strptime(move_out, '%Y-%m-%d').date()
            else:
                # For ongoing lease, set move_out to 5 years from move_in (arbitrary long date)
                move_out_date = move_in_date + timedelta(days=365*5)
        except ValueError:
            messages.error(request, 'Invalid date format. Please use YYYY-MM-DD format')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        # Validate dates
        if move_in_date >= move_out_date:
            messages.error(request, 'Move-out date must be after move-in date')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        if move_in_date < datetime.now().date():
            messages.error(request, 'Move-in date cannot be in the past')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        # Check availability
        if not apartment.is_available_for_lease(move_in_date, move_out_date):
            messages.error(request, 'This apartment is not available for the selected dates. Please choose different dates.')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        # Validate occupant count
        if num_occupants > apartment.max_occupants:
            messages.error(request, f'This apartment can only accommodate up to {apartment.max_occupants} occupants')
            return render(request, 'lease_apartment.html', {'apartment': apartment})
        
        # Calculate whole months and total price (no external dateutil dependency)
        months = _whole_months_between(move_in_date, move_out_date)
        total_price = months * apartment.monthly_rent if months > 0 else apartment.monthly_rent
        
        # Create lease
        lease = Lease.objects.create(
            tenant=request.user,
            apartment=apartment,
            move_in_date=move_in_date,
            move_out_date=move_out_date,
            num_occupants=num_occupants,
            total_lease_price=total_price,
            monthly_rent=apartment.monthly_rent,
            special_requests=special_requests,
            status='pending'
        )
        Notification.objects.create(
            tenant=request.user,
            title="Lease Created",
            message=f"Your lease for Apartment {lease.apartment.unit_number} has been submitted successfully.",
            notification_type="lease"
        )
        
        # Send confirmation email
        try:
            send_lease_confirmation_email(lease)
            send_admin_notification(
                f'New Lease #{lease.id}',
                f'New lease received from {lease.tenant.username} for Apartment {apartment.unit_number}'
            )
        except Exception as e:
            print(f"Email error: {e}")
        
        messages.success(request, f'Apartment leased successfully! Total: ₱{total_price}')
        return redirect('lease_confirmation', lease_id=lease.id)
    
    # Get occupied dates for calendar
    occupied_dates = apartment.get_occupied_dates()
    
    return render(request, 'lease_apartment.html', {
        'apartment': apartment,
        'occupied_dates': occupied_dates
    })

@login_required
def lease_confirmation(request, lease_id):
    """Display lease confirmation page after tenant applies
    
    Shows:
    - Lease details summary
    - Total price calculation
    - Dates and apartment info
    - Status (pending approval)
    
    Permission: Only the tenant who created the lease can view
    """
    lease = get_object_or_404(Lease, id=lease_id, tenant=request.user)
    return render(request, 'lease_confirmation.html', {'lease': lease})

@login_required
def cancel_lease(request, lease_id):
    """Cancel an existing lease (only if pending or confirmed status)
    
    Allowed statuses for cancellation:
    - 'pending': Awaiting admin approval
    - 'confirmed': Approved by admin
    - 'active': Currently active lease
    
    Changes lease status to 'cancelled'
    Marks apartment as available again if lease was active
    Redirects to tenant dashboard
    
    Permission: Only lease tenant can cancel
    """
    lease = get_object_or_404(Lease, id=lease_id, tenant=request.user)
    
    if lease.status in ['confirmed', 'pending', 'active']:
        # Mark apartment as available if cancelling an active lease
        if lease.status == 'active':
            lease.apartment.is_available = True
            lease.apartment.save()
        
        lease.status = 'cancelled'
        lease.save()
        messages.success(request, 'Lease cancelled successfully')
    else:
        messages.error(request, 'Cannot cancel this lease')
    
    return redirect('dashboard')

def user_logout(request):
    """Logout user and redirect to home"""
    logout(request)
    return redirect('home')

# ============================================
# PAYMENT MANAGEMENT
# ============================================

@login_required
def add_payment(request, lease_id):
    """Handle rent payment submission - creates payment record and notifies admin"""
    # Allow staff to access any lease, but tenants can only access their own
    if request.user.is_staff:
        lease = get_object_or_404(Lease, id=lease_id)
    else:
        lease = get_object_or_404(Lease, id=lease_id, tenant=request.user)
    
    if request.method == 'POST':
        amount = float(request.POST['amount'])  # Payment amount
        payment_method = request.POST['payment_method']  # How it was paid
        transaction_id = request.POST.get('transaction_id', '')  # Reference ID
        notes = request.POST.get('notes', '')  # Optional notes
        payment_date_str = request.POST.get('payment_date')
        
        # Parse the payment date - handle multiple date formats
        payment_date = None
        if payment_date_str:
            # Try parsing as YYYY-MM-DD first
            payment_date = parse_date(payment_date_str)
            # If that fails, try parsing other common formats
            if not payment_date:
                try:
                    from datetime import datetime as dt
                    # Try parsing as "Jan. 1, 2027", "Jan 1, 2027", etc.
                    payment_date = dt.strptime(payment_date_str.replace('.', ''), '%b %d, %Y').date()
                except ValueError:
                    try:
                        # Try parsing as "01/01/2027"
                        payment_date = dt.strptime(payment_date_str, '%m/%d/%Y').date()
                    except ValueError:
                        payment_date = None
        
        # Create payment record in database
        payment = RentPayment.objects.create(
            lease=lease,
            amount=amount,
            payment_method=payment_method,
            payment_status='paid',
            transaction_id=transaction_id,
            notes=notes,
            payment_date=payment_date if payment_date else datetime.now().date()
        )
        
        # Mark corresponding RentDueDate as paid if it exists
        if payment_date:
            try:
                due_date = RentDueDate.objects.get(
                    lease=lease,
                    tenant=lease.tenant,
                    due_date=payment_date
                )
                due_date.is_paid = True
                due_date.save()
            except RentDueDate.DoesNotExist:
                pass
        
        # Send payment confirmation email to tenant
        try:
            send_payment_confirmation_email(payment)
        except Exception as e:
            print(f"Email error: {e}")
        
        # Create notification for all admin users - alerts them of new payment
        from django.contrib.auth.models import User
        admin_users = User.objects.filter(is_staff=True)
        tenant_name = f"{lease.tenant.first_name} {lease.tenant.last_name}".strip() or lease.tenant.username
        
        for admin in admin_users:
            Notification.objects.create(
                tenant=admin,
                title=f"Payment Received - Lease #{lease.id}",
                message=f"₱{amount} received from {tenant_name} for Unit {lease.apartment.unit_number if lease.apartment else 'N/A'}",
                notification_type='payment'
            )
        
        messages.success(request, f'Payment of ₱{amount} recorded successfully!')
        return redirect('lease_detail', lease_id=lease.id)
    
    # Get unpaid rent due dates for this lease
    unpaid_dues = RentDueDate.objects.filter(lease=lease, is_paid=False).order_by('-due_date')
    balance = lease.get_balance()
    return render(request, 'add_payment.html', {
        'lease': lease, 
        'balance': balance,
        'unpaid_dues': unpaid_dues
    })

@login_required
def lease_detail(request, lease_id):
    """Display complete lease details and payment history for tenant or admin
    
    Shows:
    - Lease information (dates, price, apartment details)
    - Payment summary (total paid, outstanding balance)
    - Payment history with transactions
    - Add payment button
    
    Permission: Tenant can view own lease, admin can view all
    Real-time updates via AJAX every 15 seconds to refresh payment totals
    """
    lease = get_object_or_404(Lease, id=lease_id)
    
    # Only allow access if user is the lease owner or is staff
    if lease.tenant != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this lease')
        return redirect('dashboard')
    
    # Get all payments for this lease, sorted by date descending (newest first)
    payments = lease.payments.all().order_by('-payment_date')
    return render(request, 'lease_detail.html', {
        'lease': lease,
        'payments': payments
    })

# ============================================
# ADMIN DASHBOARD & ANALYTICS
# ============================================

@staff_member_required
def admin_dashboard(request):
    """Admin dashboard - shows statistics, recent activity, and analytics graphs"""
    # Check if user is staff/admin
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access this page')
        return redirect('home')
    
    # Get key statistics
    total_leases = Lease.objects.count()  # Total leases in system
    confirmed_leases = Lease.objects.filter(status='active').count()  # Active leases
    pending_leases = Lease.objects.filter(status='pending').count()  # Awaiting approval
    total_revenue = Lease.objects.filter(status__in=['active', 'completed']).aggregate(Sum('total_lease_price'))['total_lease_price__sum'] or 0  # Total lease value
    total_payments = RentPayment.objects.filter(payment_status='paid').aggregate(Sum('amount'))['amount__sum'] or 0  # Total rent collected
    
    # Get recent leases for activity feed
    recent_leases = Lease.objects.all().order_by('-created_at')[:10]
    
    # Get all apartments for filtering
    rooms = Apartment.objects.all()
    
    # ===== ANALYTICS: Support optional date range and apartment filters =====
    today = datetime.now().date()
    
    # Parse date filters from GET parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    apartment_id = request.GET.get('apartment_id')

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to 6 months ago if not specified
            start_date = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
    except ValueError:
        start_date = (today.replace(day=1) - timedelta(days=180)).replace(day=1)

    try:
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to today
            end_date = today
    except ValueError:
        end_date = today

    # apply apartment filter where necessary
    lease_base_qs = Lease.objects.filter(status__in=['confirmed', 'completed'])
    payment_base_qs = RentPayment.objects.filter(payment_status='paid')
    if apartment_id:
        lease_base_qs = lease_base_qs.filter(apartment_id=apartment_id)
        payment_base_qs = payment_base_qs.filter(lease__apartment_id=apartment_id)

    # Build month buckets from start_date to end_date (inclusive)
    months = []
    sales_data = []
    leases_count = []

    cur = start_date.replace(day=1)
    # limit to 24 months to avoid huge loops
    months_limit = 24
    cnt = 0
    while cur <= end_date and cnt < months_limit:
        months.append(cur.strftime('%b %Y'))
        # next month
        if cur.month == 12:
            next_month = cur.replace(year=cur.year + 1, month=1, day=1)
        else:
            next_month = cur.replace(month=cur.month + 1, day=1)

        month_revenue = lease_base_qs.filter(
            created_at__date__gte=cur,
            created_at__date__lt=next_month
        ).aggregate(total=Sum('total_lease_price'))['total'] or 0
        month_leases = lease_base_qs.filter(
            created_at__date__gte=cur,
            created_at__date__lt=next_month
        ).count()
        sales_data.append(float(month_revenue))
        leases_count.append(month_leases)

        cur = next_month
        cnt += 1

    # Top rooms by revenue (respecting optional apartment filter - if apartment filter present, show that single room)
    top_rooms_qs = Lease.objects.filter(status__in=['active', 'completed'])
    if apartment_id:
        top_rooms_qs = top_rooms_qs.filter(apartment_id=apartment_id)
    top_rooms_qs = top_rooms_qs.values('apartment__unit_number').annotate(revenue=Sum('total_lease_price')).order_by('-revenue')[:5]
    top_rooms = [{'room': r['apartment__unit_number'], 'revenue': float(r['revenue'] or 0)} for r in top_rooms_qs]

    avg_lease_value = float(total_revenue) / confirmed_leases if confirmed_leases else 0

    # Occupancy over last 30 days (respect apartment filter)
    period_start = today - timedelta(days=30)
    booked_nights = 0
    occ_qs = Lease.objects.filter(status='active')
    if apartment_id:
        occ_qs = occ_qs.filter(apartment_id=apartment_id)
    for b in occ_qs.filter(move_out_date__gt=period_start):
        start = max(b.move_in_date, period_start)
        end = min(b.move_out_date, today)
        if end > start:
            booked_nights += (end - start).days

    total_room_nights = (rooms.count() if rooms.count() else 1) * 30
    occupancy_rate = round((booked_nights / total_room_nights) * 100, 1)

    # Payments breakdown by method for the same filter period
    payments_qs = payment_base_qs.filter(payment_date__date__gte=start_date, payment_date__date__lte=end_date)
    payments_by_method = payments_qs.values('payment_method').annotate(total=Sum('amount'))
    payments_labels = [p['payment_method'] for p in payments_by_method]
    payments_data = [float(p['total'] or 0) for p in payments_by_method]
    
    context = {
        'total_leases': total_leases,
        'confirmed_leases': confirmed_leases,
        'pending_leases': pending_leases,
        'total_revenue': total_revenue,
        'total_payments': total_payments,
        'recent_leases': recent_leases,
        'apartments': rooms,
        'sales_labels': json.dumps(months),
        'sales_data': json.dumps(sales_data),
        'top_rooms': top_rooms,
        'avg_lease_value': avg_lease_value,
        'occupancy_rate': occupancy_rate,
        'filter_start_date': start_date.isoformat(),
        'filter_end_date': end_date.isoformat(),
        'filter_apartment_id': apartment_id,
        'leases_labels': json.dumps(months),
        'leases_data': json.dumps(leases_count),
        'payments_labels': json.dumps(payments_labels),
        'payments_data': json.dumps(payments_data),
    }
    
    return render(request, 'admin_dashboard.html', context)

@staff_member_required
def export_sales_csv(request):
    """Export filtered lease sales data as CSV file for analysis
    
    Filters: Same as admin dashboard (start_date, end_date, apartment_id)
    Output: CSV file with lease data and total revenue
    
    Columns: Lease ID, Tenant, Room, Check In, Check Out, Duration, Price, Status, Created At
    
    Use case: Admin can export sales reports for accounting and analysis
    """
    # parse same filters as dashboard
    today = datetime.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    apartment_id = request.GET.get('apartment_id')

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
    except ValueError:
        start_date = (today.replace(day=1) - timedelta(days=180)).replace(day=1)

    try:
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = today
    except ValueError:
        end_date = today

    qs = Lease.objects.filter(status__in=['confirmed', 'completed'], created_at__date__gte=start_date, created_at__date__lte=end_date)
    if apartment_id:
        qs = qs.filter(apartment_id=apartment_id)

    # prepare CSV response
    filename = f"sales_{start_date.isoformat()}_to_{end_date.isoformat()}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # header metadata
    writer.writerow(['Casa de Liberty - Sales Export'])
    writer.writerow([f'Period: {start_date.isoformat()} to {end_date.isoformat()}'])
    if apartment_id:
        try:
            apartment = Apartment.objects.get(id=apartment_id)
            writer.writerow([f'Room: {apartment.unit_number}'])
        except Apartment.DoesNotExist:
            writer.writerow([f'Room: {apartment_id}'])
    writer.writerow([])

    # column headers
    writer.writerow(['Lease ID', 'Tenant', 'Room', 'Check In', 'Check Out', 'Nights', 'Total Price', 'Status', 'Created At'])

    total_revenue = 0
    for b in qs.order_by('created_at'):
        nights = (b.move_out_date - b.move_in_date).days
        writer.writerow([b.id, b.tenant.username, b.apartment.unit_number if b.apartment else '', b.move_in_date.isoformat(), b.move_out_date.isoformat(), nights, float(b.total_lease_price), b.status, b.created_at.isoformat()])
        total_revenue += float(b.total_lease_price)

    writer.writerow([])
    writer.writerow(['', '', '', '', '', 'Total Revenue', total_revenue])

    return response


@staff_member_required
def export_sales_pdf(request):
    """Export filtered lease sales data as PDF report
    
    Filters: Same as admin dashboard (start_date, end_date, apartment_id)
    Output: Formatted PDF file with lease table and summary statistics
    
    Requires: ReportLab library (pip install reportlab)
    Use case: Admin can print or email sales reports to management
    """
    if not REPORTLAB_AVAILABLE:
        messages.error(request, 'PDF export requires ReportLab (pip install reportlab)')
        return redirect('admin_dashboard')

    today = datetime.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    apartment_id = request.GET.get('apartment_id')

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
    except ValueError:
        start_date = (today.replace(day=1) - timedelta(days=180)).replace(day=1)

    try:
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = today
    except ValueError:
        end_date = today

    qs = Lease.objects.filter(status__in=['confirmed', 'completed'], created_at__date__gte=start_date, created_at__date__lte=end_date)
    if apartment_id:
        qs = qs.filter(apartment_id=apartment_id)

    # Build PDF
    buffer = HttpResponse(content_type='application/pdf')
    filename = f"sales_{start_date.isoformat()}_to_{end_date.isoformat()}.pdf"
    buffer['Content-Disposition'] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph('Casa de Liberty - Sales Report', styles['Title'])
    elements.append(title)
    meta = Paragraph(f'Period: {start_date.isoformat()} to {end_date.isoformat()}', styles['Normal'])
    elements.append(Spacer(1, 6))
    elements.append(meta)
    elements.append(Spacer(1, 12))

    data = [['Lease ID', 'Tenant', 'Room', 'Check In', 'Check Out', 'Nights', 'Total Price', 'Status', 'Created At']]
    total_revenue = 0
    for b in qs.order_by('created_at'):
        nights = (b.move_out_date - b.move_in_date).days
        data.append([str(b.id), b.tenant.username, b.apartment.unit_number if b.apartment else '', b.move_in_date.isoformat(), b.move_out_date.isoformat(), str(nights), f'₱{float(b.total_lease_price):.2f}', b.status, b.created_at.strftime('%Y-%m-%d %H:%M')])
        total_revenue += float(b.total_lease_price)

    data.append(['', '', '', '', '', '', f'Total: ₱{total_revenue:.2f}', '', ''])

    table = Table(data, repeatRows=1)
    table.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ])

    elements.append(table)
    doc.build(elements)
    return buffer

@staff_member_required
def manage_leases(request):
    """Admin view to manage all leases - approve, reject, update status
    
    Shows:
    - All leases in the system ordered by newest first
    - Pending leases highlighted (leases awaiting approval)
    - Filter by status: pending, active, cancelled, completed
    - Each lease with tenant info, dates, and price
    
    Admin actions:
    - Click lease to view details and update status
    - Approve pending leases (change from pending→active)
    - Complete leases (change from active→completed)
    - Cancel leases if needed
    
    Status workflow: pending → active → completed (or cancelled)
    """
    # Get all leases
    all_leases = Lease.objects.all().order_by('-created_at')
    
    # Get pending leases separately for emphasis
    pending_leases = all_leases.filter(status='pending')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        all_leases = all_leases.filter(status=status_filter)
    
    return render(request, 'manage_leases.html', {
        'leases': all_leases,
        'pending_leases': pending_leases,
        'pending_count': pending_leases.count()
    })

@staff_member_required
def manage_apartments(request):
    """Admin view to manage all apartments - view, edit, create new units
    
    Shows:
    - All apartments in system with details
    - Unit number, type, rent price, max occupants
    - Availability status
    - Edit/delete options
    
    Admin actions:
    - Create new apartment (form available)
    - Edit existing apartment details (price, availability, etc.)
    - Delete apartment
    - Mark as available/unavailable
    """
    rooms = Apartment.objects.all()
    return render(request, 'manage_apartments.html', {'apartments': rooms, 'messages': messages.get_messages(request)})


@staff_member_required
def manage_tenants(request):
    """Display all tenants with their account info, balance, and nearest due date"""
    from .models import RentDueDate
    
    # Get all non-staff users (tenants)
    tenants = User.objects.filter(is_staff=False).select_related('profile')
    
    # Build tenant data with balances and due dates
    tenant_data = []
    for tenant in tenants:
        try:
            profile = tenant.profile
        except UserProfile.DoesNotExist:
            profile = None
        
        # Get all unpaid rent due dates for this tenant
        unpaid_dues = RentDueDate.objects.filter(tenant=tenant, is_paid=False).order_by('due_date')
        
        # Calculate total remaining balance
        total_balance = unpaid_dues.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        
        # Get nearest due date (upcoming or overdue)
        nearest_due = unpaid_dues.first() if unpaid_dues.exists() else None
        
        # Get active leases
        active_leases = Lease.objects.filter(tenant=tenant, status__in=['active', 'pending']).count()
        
        tenant_data.append({
            'user': tenant,
            'profile': profile,
            'contact_number': profile.contact_number if profile else 'N/A',
            'email': tenant.email or 'Not set',
            'total_balance': total_balance,
            'nearest_due_date': nearest_due.due_date if nearest_due else None,
            'active_leases': active_leases,
            'status': 'Active' if active_leases > 0 else 'Inactive'
        })
    
    return render(request, 'manage_tenants.html', {'tenant_data': tenant_data})

# ============================================
# APARTMENT & PROPERTY MANAGEMENT
# ============================================

# Custom view to handle apartment creation from the admin dashboard
from django.core.exceptions import ValidationError

@staff_member_required
def add_apartment(request):
    """Admin creates new apartment unit in the system
    
    POST: Create new Apartment with:
    - Unit number (required, must be unique)
    - Type (Studio, 1BR, 2BR, etc.)
    - Monthly rent price (required, must be > 0)
    - Max occupants (required, must be > 0)
    - Description (required, detailed info)
    - Amenities (optional, comma-separated list)
    - Image URL (optional, photo of apartment)
    - Status: is_available=True (all new apartments available)
    
    Validation:
    - All required fields present
    - Unit number not already in use
    - Rent and occupants are valid numbers
    
    On success: Create Apartment, redirect to manage_apartments
    On error: Show message and redirect to manage_apartments
    """
    if request.method == 'POST':
        unit_number = request.POST.get('unit_number')
        apartment_type = request.POST.get('apartment_type')
        monthly_rent = request.POST.get('monthly_rent')
        max_occupants = request.POST.get('max_occupants')
        description = request.POST.get('description')
        amenities = request.POST.get('amenities', '')
        image_url = request.POST.get('image_url', '')

        # Validate required fields
        if not all([unit_number, apartment_type, monthly_rent, max_occupants, description]):
            messages.error(request, 'All fields except image URL and amenities are required.')
            return redirect('manage_apartments')

        # Check for duplicate apartment number
        if Apartment.objects.filter(unit_number=unit_number).exists():
            messages.error(request, f'Apartment unit {unit_number} already exists.')
            return redirect('manage_apartments')

        try:
            monthly_rent = float(monthly_rent)
            max_occupants = int(max_occupants)
            
            if monthly_rent <= 0:
                messages.error(request, 'Monthly rent must be greater than 0.')
                return redirect('manage_apartments')
            
            if max_occupants <= 0:
                messages.error(request, 'Max occupants must be greater than 0.')
                return redirect('manage_apartments')
            
            apartment = Apartment.objects.create(
                unit_number=unit_number,
                apartment_type=apartment_type,
                monthly_rent=monthly_rent,
                max_occupants=max_occupants,
                description=description,
                amenities=amenities,
                image_url=image_url,
                is_available=True
            )
            
            # Feb 24 behavior was URL-based apartment photos. Prefer URLs, but
            # keep newer file uploads working for compatibility.
            raw_photo_url_values = [
                request.POST.get('photo_urls', ''),
                request.POST.get('initial_photo_urls', ''),
                request.POST.get('photo_url_1', ''),
                request.POST.get('photo_url_2', ''),
                request.POST.get('photo_url_3', ''),
                request.POST.get('photo_url_4', ''),
            ]
            photo_count = 0

            for order, photo_url in enumerate(_normalized_photo_urls(raw_photo_url_values)[:4]):
                try:
                    ApartmentPhoto.objects.create(
                        apartment=apartment,
                        photo_url=photo_url,
                        photo_order=order
                    )
                    photo_count += 1
                except Exception as photo_error:
                    # Log but don't fail - apartment is already created
                    print(f"Error saving photo URL: {photo_error}")

            photos = request.FILES.getlist('initial_photos')
            remaining_slots = max(0, 4 - photo_count)
            for offset, photo in enumerate(photos[:remaining_slots]):
                try:
                    ApartmentPhoto.objects.create(
                        apartment=apartment,
                        photo=photo,
                        photo_order=photo_count + offset
                    )
                    photo_count += 1
                except Exception as photo_error:
                    # Log but don't fail - apartment is already created
                    print(f"Error uploading photo: {photo_error}")

            if photo_count > 0:
                messages.success(request, f'Apartment {unit_number} created successfully with {photo_count} photo(s)!')
            else:
                messages.success(request, f'Apartment {unit_number} created successfully!')
        except ValueError as e:
            messages.error(request, f'Invalid input: Monthly rent and max occupants must be numbers.')
        except ValidationError as e:
            messages.error(request, f'Error: {e}')
        except Exception as e:
            messages.error(request, f'Unexpected error: {e}')
        return redirect('manage_apartments')
    else:
        return redirect('manage_apartments')

@staff_member_required
def update_lease_status(request, lease_id):
    """Admin update lease status and create monthly rent due dates
    
    POST: Change lease status (pending→active→completed→etc)
    - Generate RentDueDate records for each month when lease becomes active
    - Create notifications to tenant about status change
    - Send email notification
    - On error: Show message and redirect
    
    Workflow: 
    - pending → active: Creates monthly rent due dates for lease period
    - active → completed: Marks lease as finished
    - completed/pending → cancelled: Cancels lease
    """
    lease = get_object_or_404(Lease, id=lease_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        old_status = lease.status
        
        # Validate status choice
        valid_statuses = [choice[0] for choice in Lease.STATUS_CHOICES]
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid lease status')
            return redirect('manage_leases')
        
        lease.status = new_status
        lease.save()
        
        # Send notification to tenant
        if old_status == 'pending' and new_status == 'active':
            # Mark apartment as unavailable when lease is activated
            lease.apartment.is_available = False
            lease.apartment.save()
            
            # Create monthly rent due dates for the lease period

            # First payment is due one month after move-in date, on the same day
            # E.g., if move-in is Jan 2, first payment due is Feb 2
            first_payment_date = _add_months(lease.move_in_date, 1)
            current_date = first_payment_date
            month_count = 0
            
            while current_date <= lease.move_out_date:
                # Create due date - payment is due on the same day of the month as move-in date
                try:
                    due_date = current_date.replace(day=lease.move_in_date.day)
                except ValueError:
                    # Handle case where day doesn't exist in that month (e.g., Jan 31 -> Feb 31)
                    # Use the last day of the month instead
                    due_date = _last_day_of_month(current_date)
                
                # Only create if due date is within lease period and after move-in date
                if due_date > lease.move_in_date and due_date <= lease.move_out_date:
                    RentDueDate.objects.get_or_create(
                        lease=lease,
                        tenant=lease.tenant,
                        due_date=due_date,
                        defaults={
                            'amount_due': lease.monthly_rent,
                            'is_paid': False,
                            'is_recurring_monthly': True
                        }
                    )
                    month_count += 1
                
                # Move to next month
                current_date = _add_months(current_date, 1)
            
            Notification.objects.create(
                tenant=lease.tenant,
                title='Lease Approved',
                message=f'Your lease for Apartment {lease.apartment.unit_number} has been approved by the admin. Your lease is now active! {month_count} monthly payment due dates have been created.',
                notification_type='lease'
            )
            messages.success(request, f'Lease #{lease_id} approved and activated with {month_count} monthly payment due dates created')
        elif new_status == 'terminated':
            # Mark apartment as available again when lease is terminated
            lease.apartment.is_available = True
            lease.apartment.save()
            
            Notification.objects.create(
                tenant=lease.tenant,
                title='Lease Terminated',
                message=f'Your lease for Apartment {lease.apartment.unit_number} has been terminated by the admin.',
                notification_type='lease'
            )
            messages.warning(request, f'Lease #{lease_id} terminated')
        elif new_status == 'completed':
            # Mark apartment as available again when lease is completed
            lease.apartment.is_available = True
            lease.apartment.save()
            
            Notification.objects.create(
                tenant=lease.tenant,
                title='Lease Completed',
                message=f'Your lease for Apartment {lease.apartment.unit_number} has been marked as completed.',
                notification_type='lease'
            )
            messages.success(request, f'Lease #{lease_id} completed')
        elif new_status == 'cancelled' and old_status == 'active':
            # Mark apartment as available again if cancelling an active lease
            lease.apartment.is_available = True
            lease.apartment.save()
            
            Notification.objects.create(
                tenant=lease.tenant,
                title='Lease Cancelled',
                message=f'Your lease for Apartment {lease.apartment.unit_number} has been cancelled.',
                notification_type='lease'
            )
            messages.warning(request, f'Lease #{lease_id} cancelled')
        else:
            messages.info(request, f'Lease #{lease_id} status updated to {lease.get_status_display()}')
        
        return redirect('manage_leases')
    return redirect('manage_leases')

@staff_member_required
def toggle_apartment_availability(request, apartment_id):
    apartment = get_object_or_404(Apartment, id=apartment_id)
    apartment.is_available = not apartment.is_available
    apartment.save()
    
    status = "available" if apartment.is_available else "unavailable"
    messages.success(request, f'Apartment {apartment.unit_number} is now {status}')
    return redirect('manage_apartments')

def check_availability(request):
    """AJAX endpoint to check apartment availability for a date range
    
    Parameters:
    - apartment_id: ID of apartment to check
    - move_in: Move-in date (YYYY-MM-DD format)
    - move_out: (optional) Move-out date for multi-day booking
    
    Returns JSON:
    - available: Boolean - true if dates don't conflict with existing leases
    - monthly_rent: Float - rent price for calculation
    - error: String (if invalid request)
    
    Used by: lease_apartment form to validate dates in real-time
    """
    apartment_id = request.GET.get('apartment_id')
    move_in = request.GET.get('move_in')
    
    if not all([apartment_id, move_in]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        apartment = Apartment.objects.get(id=apartment_id)
        move_in_date = datetime.strptime(move_in, '%Y-%m-%d').date()
        
        is_available = apartment.is_available_for_lease(move_in_date)
        
        return JsonResponse({
            'available': is_available,
            'monthly_rent': float(apartment.monthly_rent),
        })
    except Apartment.DoesNotExist:
        return JsonResponse({'error': 'Apartment not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

@login_required
def my_leases(request):
    """Tenant view of all their leases - current and past
    
    Shows:
    - All leases created by this tenant
    - Lease status (pending, active, completed, cancelled)
    - Dates, apartment, total price
    - Links to lease detail for more information
    
    From lease detail page, tenant can:
    - View payment history
    - Make new payments
    - View maintenance requests
    
    Ordered by newest first
    """
    leases = Lease.objects.filter(tenant=request.user).order_by('-created_at')
    return render(request, 'my_leases.html', {'leases': leases})

@login_required
def payments(request):
    from datetime import timedelta
    
    leases = Lease.objects.filter(tenant=request.user).select_related('apartment').order_by('-created_at')
    rent_payments = RentPayment.objects.filter(lease__tenant=request.user).select_related('lease', 'lease__apartment').order_by('-payment_date')
    
    # Show only unpaid dues in the next 6 months (upcoming payments)
    today = datetime.now().date()
    six_months_later = today + timedelta(days=180)
    rent_due_dates = RentDueDate.objects.select_related('lease', 'lease__apartment').filter(
        tenant=request.user,
        is_paid=False,
        due_date__gte=today,
        due_date__lte=six_months_later
    ).order_by('due_date')
    
    # Get count of all unpaid dues for reference
    all_unpaid_dues_qs = RentDueDate.objects.filter(
        tenant=request.user,
        is_paid=False
    )
    all_unpaid_dues_count = all_unpaid_dues_qs.count()

    paid_payments_qs = rent_payments.filter(payment_status='paid')

    total_due = leases.aggregate(total=Sum('total_lease_price'))['total'] or 0
    total_paid = paid_payments_qs.aggregate(total=Sum('amount'))['total'] or 0
    outstanding_balance = all_unpaid_dues_qs.aggregate(total=Sum('amount_due'))['total'] or (total_due - total_paid)
    upcoming_due_total = rent_due_dates.aggregate(total=Sum('amount_due'))['total'] or 0
    active_leases_count = leases.filter(status='active').count()
    paid_payments_count = paid_payments_qs.count()
    
    return render(request, 'payments.html', {
        'leases': leases, 
        'rent_payments': rent_payments,
        'rent_due_dates': rent_due_dates,
        'all_unpaid_dues_count': all_unpaid_dues_count,
        'total_due': total_due,
        'total_paid': total_paid,
        'outstanding_balance': outstanding_balance,
        'upcoming_due_total': upcoming_due_total,
        'active_leases_count': active_leases_count,
        'paid_payments_count': paid_payments_count,
    })

# ============================================
# MAINTENANCE REQUEST MANAGEMENT
# ============================================

@login_required
def maintenance(request):
    """Tenant submits maintenance requests - plumbing, electrical, cleaning, etc."""
    if request.method == 'POST':
        maintenance_type = request.POST.get('maintenance_type')  # Type of maintenance needed
        description = request.POST.get('description')  # Detailed description
        priority = request.POST.get('priority', 'medium')  # Urgency level
        
        # Apartment is optional - not required for general maintenance
        apartment = None
        
        # Create maintenance request in database
        maintenance = Maintenance.objects.create(
            tenant=request.user,
            apartment=apartment,
            maintenance_type=maintenance_type,
            description=description,
            priority=priority
        )
        
        # Create in-app notification for staff/admin alerting them
        room_info = f"Apartment {maintenance.apartment.unit_number}" if maintenance.apartment else "General"
        Notification.objects.create(
            tenant=request.user,
            title=f"Maintenance #{maintenance.id} Submitted",
            message=f"New maintenance request for {room_info} submitted.",
            notification_type='system'
        )
        
        # Send email notifications to admin and tenant (fail silently if email fails)
        try:
            context = {'maintenance': maintenance}
            # Email to admin
            admin_subject = f"New Maintenance Request #{maintenance.id}"
            admin_text = render_to_string('emails/maintenance_submitted.txt', context)
            admin_html = render_to_string('emails/maintenance_submitted.html', context)
            admin_msg = EmailMultiAlternatives(admin_subject, admin_text, settings.DEFAULT_FROM_EMAIL, [getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)])
            admin_msg.attach_alternative(admin_html, 'text/html')
            admin_msg.send()
            
            # Confirmation email to tenant
            if maintenance.tenant.email:
                user_subject = f"Maintenance Request #{maintenance.id} Received"
                user_text = render_to_string('emails/maintenance_submitted_user.txt', context)
                user_html = render_to_string('emails/maintenance_submitted_user.html', context)
                user_msg = EmailMultiAlternatives(user_subject, user_text, settings.DEFAULT_FROM_EMAIL, [maintenance.tenant.email])
                user_msg.attach_alternative(user_html, 'text/html')
                user_msg.send()
        except Exception:
            pass  # Fail silently - don't break the request if email fails
        
        messages.success(request, f'Maintenance request #{maintenance.id} submitted successfully!')
        return redirect('maintenance')
    
    # Get user's rooms from active leases
    active_leases = Lease.objects.filter(
        tenant=request.user,
        status='active',
        move_in_date__lte=datetime.now().date(),
        move_out_date__gt=datetime.now().date()
    )
    user_rooms = Apartment.objects.filter(lease__in=active_leases).distinct()
    user_maintenance = Maintenance.objects.filter(tenant=request.user, is_cleared=False).order_by('-created_at')
    maintenance_counts = user_maintenance.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='pending')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        completed=Count('id', filter=Q(status='completed')),
        cancelled=Count('id', filter=Q(status='cancelled')),
    )
    
    context = {
        'apartments': user_rooms,
        'maintenance_requests': user_maintenance,
        'maintenance_types': Maintenance._meta.get_field('maintenance_type').choices,
        'maintenance_counts': maintenance_counts,
    }
    
    return render(request, 'maintenance.html', context)


@staff_member_required
def staff_maintenance_list(request):
    """Admin view to list all pending maintenance requests in FIFO order
    
    Shows:
    - All maintenance requests that haven't been cleared (is_cleared=False)
    - Ordered by created_at (oldest first = FIFO)
    - Tenant name, maintenance type, description, priority, status
    - Created date and assigned apartment (if any)
    
    Admin actions:
    - Click request to update status (pending→in_progress→completed)
    - Add/update notes as work progresses
    - Mark completed to set completion timestamp
    - Soft-delete by clearing requests (is_cleared=True)
    
    Workflow: Created → In Progress → Completed → Cleared
    """
    maint_requests = Maintenance.objects.select_related('tenant', 'apartment', 'lease').filter(is_cleared=False).order_by('-created_at')
    status_counts = maint_requests.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='pending')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        completed=Count('id', filter=Q(status='completed')),
        cancelled=Count('id', filter=Q(status='cancelled')),
    )
    return render(request, 'staff_maintenance.html', {
        'maintenance_requests': maint_requests,
        'status_counts': status_counts,
    })


@staff_member_required
def staff_maintenance_action(request, maintenance_id):
    """Handle admin status updates for maintenance requests"""
    maint = get_object_or_404(Maintenance, id=maintenance_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        # Validate status
        valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status')
            return redirect('staff_maintenance')
        
        old_status = maint.status
        maint.status = new_status
        
        # Update notes if provided
        if notes:
            maint.notes = notes
        
        # Set completed_at if marking as completed
        if new_status == 'completed' and not maint.completed_at:
            maint.completed_at = datetime.now()
        
        maint.save()
        
        # Create notification for tenant based on status
        status_messages = {
            'in_progress': f"Your maintenance request #{maint.id} is now in progress.",
            'completed': f"Your maintenance request #{maint.id} has been completed.",
            'cancelled': f"Your maintenance request #{maint.id} has been cancelled.",
            'pending': f"Your maintenance request #{maint.id} is pending review."
        }
        
        notification_msg = status_messages.get(new_status, f"Maintenance request #{maint.id} status updated to {new_status}")
        
        Notification.objects.create(
            tenant=maint.tenant,
            title=f"Maintenance #{maint.id} - {new_status.replace('_', ' ').title()}",
            message=notification_msg,
            notification_type='system'
        )
        
        # Send email to tenant
        try:
            if maint.tenant.email:
                subject = f"Maintenance Request #{maint.id} - {new_status.replace('_', ' ').title()}"
                context = {
                    'maintenance': maint,
                    'status': new_status,
                    'notes': notes
                }
                text_body = render_to_string('emails/maintenance_status.txt', context)
                html_body = render_to_string('emails/maintenance_status.html', context)
                msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [maint.tenant.email])
                msg.attach_alternative(html_body, "text/html")
                msg.send()
        except Exception as e:
            # don't block admin action if email fails
            pass
        
        messages.success(request, f'Maintenance request #{maint.id} status updated to {new_status.replace("_", " ").title()}')
        return redirect('staff_maintenance')

    return render(request, 'staff_maintenance_detail.html', {'maintenance': maint})


@csrf_protect
@staff_member_required
def clear_maintenance_request(request, maintenance_id):
    """Clear (archive) a maintenance request - removes from view but keeps in database"""
    try:
        maint = Maintenance.objects.get(id=maintenance_id)
        maint.is_cleared = True
        maint.save()
        
        # Create notification for tenant
        Notification.objects.create(
            tenant=maint.tenant,
            title=f"Maintenance #{maint.id} - Cleared",
            message=f"Your maintenance request #{maint.id} has been cleared from your active requests.",
            notification_type='system'
        )
        
        return JsonResponse({'success': True, 'message': f'Maintenance request #{maint.id} cleared'})
    except Maintenance.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Maintenance request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def notifications(request):
    notifications = Notification.objects.filter(tenant=request.user).order_by('-created_at')

    return render(request, 'notifications.html', {
        'notifications': notifications
    })

@login_required
def api_notification_count(request):
    """API endpoint to get unread notification count"""
    count = Notification.objects.filter(tenant=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required
def api_mark_notification_read(request, notification_id):
    """API endpoint to mark a notification as read"""
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, tenant=request.user)
            notification.is_read = True
            notification.save()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

@login_required
def api_due_dates_count(request):
    """API endpoint - returns count of unpaid overdue payments for badge notification"""
    count = RentDueDate.objects.filter(lease__tenant=request.user, is_paid=False, due_date__lte=datetime.now().date()).count()
    return JsonResponse({'count': count})


# ============================================
# API ENDPOINTS (AJAX / Real-time data)
# ============================================

@staff_member_required
def api_payment_notifications(request):
    """API endpoint - returns recent payment notifications (last 24 hours) for admin dashboard"""
    # Get recent payment notifications (last 24 hours only)
    from datetime import timedelta
    recent_time = datetime.now() - timedelta(hours=24)
    
    # Fetch notifications for current admin user
    notifications = Notification.objects.filter(
        tenant=request.user,
        notification_type='payment',
        created_at__gte=recent_time
    ).order_by('-created_at')[:5]
    
    # Format data for JSON response
    data = {
        'notifications': [
            {
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'timestamp': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': notif.is_read
            }
            for notif in notifications
        ],
        'count': Notification.objects.filter(
            tenant=request.user,
            notification_type='payment',
            is_read=False
        ).count()  # Total unread count
    }
    return JsonResponse(data)


@login_required
def api_lease_payment_summary(request, lease_id):
    """API endpoint - returns current payment totals for lease (used for real-time updates)"""
    try:
        lease = Lease.objects.get(id=lease_id)
        
        # Permission check - tenant can only view own lease, staff can view all
        if lease.tenant != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Calculate payment totals
        total_paid = lease.get_total_paid_rent() or 0
        outstanding_balance = lease.get_outstanding_balance() or 0
        
        # Format response data
        data = {
            'lease_id': lease.id,
            'total_paid': str(total_paid),
            'outstanding_balance': str(outstanding_balance),
            'monthly_rent': str(lease.apartment.monthly_rent),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return JsonResponse(data)
    except Lease.DoesNotExist:
        return JsonResponse({'error': 'Lease not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Calendar System Views
from .models import Event, RentDueDate, TimeOff
import json
from django.http import JsonResponse
from datetime import date, datetime, timedelta
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie

@staff_member_required
def admin_calendar(request):
    """Admin view all system events - calendar of everything
    
    Displays:
    - Admin events (green): Created by admin, always approved
    - Pending requests (yellow): Tenant requests awaiting approval
    - Approved events (blue): Tenant events admin approved
    - Days off (red): Staff availability/time off periods
    - Rent due dates: Monthly rent deadlines (gray)
    
    Admin actions:
    - Approve pending tenant requests (changes status→approved)
    - Reject pending requests (changes status→rejected)
    - Create admin events (admin-only events)
    - View all staff time off in one place
    
    Color coding: Admin=green, Pending=yellow, Approved=blue, Days Off=red, Due Dates=gray
    """
    # Get all events
    admin_events = Event.objects.filter(is_admin_event=True).order_by('event_date')
    pending_requests = Event.objects.filter(is_admin_event=False, status='pending').order_by('event_date')
    approved_tenant_events = Event.objects.filter(is_admin_event=False, status='approved').order_by('event_date')
    
    # Admin should see all tenant due dates (paid and unpaid)
    rent_dues = RentDueDate.objects.select_related('tenant', 'lease__apartment').order_by('due_date')
    
    # Get all time off periods
    staff_time_off = TimeOff.objects.filter(start_date__gte=date.today() - timedelta(days=30)).order_by('start_date')
    
    # Prepare calendar data
    calendar_events = []
    
    # Add admin events (green)
    for event in admin_events:
        calendar_events.append({
            'id': event.id,
            'title': f"[ADMIN] {event.title}",
            'date': event.event_date.isoformat(),
            'type': 'admin',
            'status': 'approved',
            'color': '#10b981',
            'description': event.description,
        })
    
    # Add pending tenant requests (yellow)
    for event in pending_requests:
        calendar_events.append({
            'id': event.id,
            'title': f"[PENDING] {event.title} - {event.requested_by.username}",
            'date': event.event_date.isoformat(),
            'type': 'tenant_request',
            'status': 'pending',
            'color': '#f59e0b',
            'description': event.description,
            'requested_by': event.requested_by.username,
        })
    
    # Add approved tenant events (blue)
    for event in approved_tenant_events:
        calendar_events.append({
            'id': event.id,
            'title': f"[TENANT] {event.title} - {event.requested_by.username}",
            'date': event.event_date.isoformat(),
            'type': 'tenant_event',
            'status': 'approved',
            'color': '#3b82f6',
            'description': event.description,
        })
    
    # Add days off (red)
    for time_off in staff_time_off:
        current = time_off.start_date
        while current <= time_off.end_date:
            calendar_events.append({
                'id': f"timeoff_{time_off.id}_{current}",
                'title': f"[DAYS OFF] {time_off.user.username}",
                'date': current.isoformat(),
                'type': 'days_off',
                'status': 'info',
                'color': '#ef4444',
                'description': time_off.reason,
            })
            current += timedelta(days=1)
    
    # Add rent due dates from actual RentDueDate rows (no synthetic recurring duplicates)
    for rent_due in rent_dues:
        amount_text = f"\u20b1{rent_due.amount_due}"
        is_paid = bool(rent_due.is_paid)
        apartment_obj = getattr(rent_due.lease, 'apartment', None)
        apartment_label = getattr(apartment_obj, 'unit_number', 'N/A')
        calendar_events.append({
            'id': f"rent_{rent_due.id}",
            'title': f"[{'PAID RENT' if is_paid else 'RENT DUE'}] {rent_due.tenant.username} - {amount_text}",
            'date': rent_due.due_date.isoformat(),
            'type': 'payment',
            'status': 'paid' if is_paid else 'pending',
            'color': '#94a3b8' if is_paid else '#ec7063',
            'description': f"Apt {apartment_label} | Amount: {amount_text}",
            'tenant': rent_due.tenant.username,
            'apartment': apartment_label,
            'payment_status': 'paid' if is_paid else 'unpaid',
        })

    # Sort calendar events by date for upcoming events display
    calendar_events_sorted = sorted(calendar_events, key=lambda x: x['date'])
    
    context = {
        'calendar_events': json.dumps(calendar_events),
        'calendar_events_sorted': calendar_events_sorted,
        'admin_events': admin_events,
        'pending_requests': pending_requests,
        'approved_tenant_events': approved_tenant_events,
        'due_payments': rent_dues,
        'staff_time_off': staff_time_off,
        'today': date.today().isoformat(),
    }
    
    return render(request, 'admin_calendar.html', context)


@staff_member_required
def add_admin_event(request):
    """Admin creates a new event"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        event_date = request.POST.get('event_date')
        event_type = request.POST.get('event_type', 'other')
        
        if not all([title, event_date]):
            messages.error(request, 'Title and date are required.')
            return redirect('admin_calendar')
        
        try:
            event = Event.objects.create(
                title=title,
                description=description,
                event_date=event_date,
                event_type=event_type,
                created_by=request.user,
                is_admin_event=True,
                status='approved',
            )
            messages.success(request, f'Event "{title}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating event: {e}')
        
        return redirect('admin_calendar')
    
    return redirect('admin_calendar')


@staff_member_required
def approve_event(request, event_id):
    """Admin approves a tenant event request"""
    event = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            event.status = 'approved'
            event.approved_at = datetime.now()
            event.save()
            
            # Notify tenant
            Notification.objects.create(
                tenant=event.requested_by,
                title='Event Approved',
                message=f'Your calendar event "{event.title}" has been approved!',
                notification_type='system'
            )
            messages.success(request, f'Event approved!')
        
        elif action == 'reject':
            event.status = 'rejected'
            event.save()
            
            # Notify tenant
            Notification.objects.create(
                tenant=event.requested_by,
                title='Event Rejected',
                message=f'Your calendar event "{event.title}" has been rejected.',
                notification_type='system'
            )
            messages.info(request, f'Event rejected!')
    
    return redirect('admin_calendar')


@staff_member_required
def delete_event(request, event_id):
    """Admin deletes an event"""
    event = get_object_or_404(Event, id=event_id)
    event.delete()
    messages.success(request, 'Event deleted successfully!')
    return redirect('admin_calendar')


@staff_member_required
def set_time_off(request):
    """Admin/staff sets time off"""
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason', '')
        
        if not all([start_date, end_date]):
            messages.error(request, 'Start and end dates are required.')
            return redirect('admin_calendar')
        
        try:
            TimeOff.objects.create(
                tenant=request.user,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
            )
            messages.success(request, 'Time off set successfully!')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        
        return redirect('admin_calendar')
    
    return redirect('admin_calendar')


@login_required
def tenant_calendar(request):
    """Tenant personal calendar view - see admin events and own events
    
    Shows:
    - Admin events (green): Approved announcements visible to all tenants
    - Tenant's approved events (blue): Their own approved requests
    - Tenant's pending requests (yellow): Awaiting admin approval
    - Rent due dates (gray): When tenant's rent payments are due
    
    Tenant actions:
    - Request new events (pending submission for admin approval)
    - View admin announcements
    - Track rent due dates
    
    Permission: Each tenant only sees their own events and all admin events
    """
    # Get all approved admin events
    admin_events = Event.objects.filter(is_admin_event=True, status='approved').order_by('event_date')
    
    # Get tenant's approved events
    tenant_events = Event.objects.filter(
        requested_by=request.user,
        status='approved'
    ).order_by('event_date')
    
    # Get tenant's pending event requests
    pending_requests = Event.objects.filter(
        requested_by=request.user,
        status='pending'
    ).order_by('event_date')
    
    # Get tenant's rent due dates
    rent_dues = RentDueDate.objects.select_related('tenant', 'lease__apartment').filter(
            tenant=request.user,
            is_paid=False,
        ).order_by('due_date')
    
    # Prepare calendar data
    calendar_events = []
    
    # Add admin events (green)
    for event in admin_events:
        calendar_events.append({
            'id': event.id,
            'title': f"[{event.get_event_type_display()}] {event.title}",
            'date': event.event_date.isoformat(),
            'type': 'admin',
            'color': '#10b981',
            'description': event.description,
        })
    
    # Add tenant's approved events (blue)
    for event in tenant_events:
        calendar_events.append({
            'id': event.id,
            'title': f"✓ {event.title}",
            'date': event.event_date.isoformat(),
            'type': 'approved',
            'color': '#3b82f6',
            'description': event.description,
        })
    
    # Add pending requests (yellow)
    for event in pending_requests:
        calendar_events.append({
            'id': event.id,
            'title': f"⏳ {event.title} (Pending)",
            'date': event.event_date.isoformat(),
            'type': 'pending',
            'color': '#f59e0b',
            'description': event.description,
        })
    
    # Add due payments (orange)
    for payment in rent_dues:
        amount_text = f"\u20b1{payment.amount_due}"
        calendar_events.append({
            'id': f"payment_{payment.id}",
            'title': f"[PAYMENT DUE] {payment.tenant.username} - {amount_text}",
            'date': payment.due_date.isoformat(),
            'type': 'payment',
            'color': '#ec7063',
            'description': f"Amount: {amount_text}",
        })

    # Sort calendar events by date for upcoming events display
    calendar_events_sorted = sorted(calendar_events, key=lambda x: x['date'])

    context = {
        'calendar_events': json.dumps(calendar_events),
        'calendar_events_sorted': calendar_events_sorted,
        'admin_events': admin_events,
        'tenant_events': tenant_events,
        'pending_requests': pending_requests,
        'due_payments': rent_dues,
        'today': date.today().isoformat(),
    }

    return render(request, 'tenant_calendar.html', context)


@login_required
@require_http_methods(["GET"])
def api_calendar_events(request):
    """Return calendar events as JSON tailored to the requesting user"""
    # Admin sees everything; tenants see approved admin events + their own
    if request.user.is_staff:
        admin_events = Event.objects.filter(is_admin_event=True).order_by('event_date')
        pending_requests = Event.objects.filter(is_admin_event=False, status='pending').order_by('event_date')
        approved_tenant_events = Event.objects.filter(is_admin_event=False, status='approved').order_by('event_date')
        rent_dues = RentDueDate.objects.select_related('tenant', 'lease__apartment').order_by('due_date')
        staff_time_off = TimeOff.objects.filter(start_date__gte=date.today() - timedelta(days=30)).order_by('start_date')
    else:
        admin_events = Event.objects.filter(is_admin_event=True, status='approved').order_by('event_date')
        pending_requests = Event.objects.filter(requested_by=request.user, status='pending').order_by('event_date')
        approved_tenant_events = Event.objects.filter(requested_by=request.user, status='approved').order_by('event_date')
        rent_dues = RentDueDate.objects.select_related('tenant', 'lease__apartment').filter(
            tenant=request.user,
            is_paid=False,
        ).order_by('due_date')
        staff_time_off = TimeOff.objects.none()

    calendar_events = []
    for event in admin_events:
        calendar_events.append({
            'id': event.id,
            'title': f"[ADMIN] {event.title}",
            'date': event.event_date.isoformat(),
            'type': 'admin',
            'status': event.status,
            'color': event.color or '#10b981',
            'description': event.description or '',
            'requested_by': getattr(event.requested_by, 'username', None)
        })

    for event in pending_requests:
        calendar_events.append({
            'id': event.id,
            'title': f"[PENDING] {event.title} - {event.requested_by.username if event.requested_by else ''}",
            'date': event.event_date.isoformat(),
            'type': 'tenant_request',
            'status': event.status,
            'color': event.color or '#f59e0b',
            'description': event.description or '',
            'requested_by': getattr(event.requested_by, 'username', None),
        })

    for event in approved_tenant_events:
        calendar_events.append({
            'id': event.id,
            'title': f"[TENANT] {event.title} - {event.requested_by.username if event.requested_by else ''}",
            'date': event.event_date.isoformat(),
            'type': 'tenant_event',
            'status': event.status,
            'color': event.color or '#3b82f6',
            'description': event.description or '',
            'requested_by': getattr(event.requested_by, 'username', None),
        })

    for time_off in staff_time_off:
        current = time_off.start_date
        while current <= time_off.end_date:
            calendar_events.append({
                'id': f"timeoff_{time_off.id}_{current}",
                'title': f"[DAYS OFF] {time_off.user.username}",
                'date': current.isoformat(),
                'type': 'days_off',
                'status': 'info',
                'color': '#ef4444',
                'description': time_off.reason or '',
            })
            current += timedelta(days=1)

    for payment in rent_dues:
        amount_text = f"\u20b1{payment.amount_due}"
        is_paid = bool(payment.is_paid)
        apartment_obj = getattr(payment.lease, 'apartment', None)
        apartment_label = getattr(apartment_obj, 'unit_number', 'N/A')
        calendar_events.append({
            'id': f"payment_{payment.id}",
            'title': f"[{'PAID RENT' if is_paid else 'PAYMENT DUE'}] {getattr(payment.tenant, 'username', '')} - {amount_text}",
            'date': payment.due_date.isoformat(),
            'type': 'payment',
            'status': 'paid' if is_paid else 'pending',
            'color': '#94a3b8' if is_paid else '#ec7063',
            'description': f"Apt {apartment_label} | Amount: {amount_text}",
            'tenant': getattr(payment.tenant, 'username', ''),
            'apartment': apartment_label,
            'payment_status': 'paid' if is_paid else 'unpaid',
        })

    return JsonResponse({'events': calendar_events})


@login_required
@require_http_methods(["POST"])
def api_create_event(request):
    """Create an event via AJAX. Admin events auto-approve; tenant events are pending."""
    title = request.POST.get('title') or request.POST.get('name')
    description = request.POST.get('description', '')
    event_date = request.POST.get('event_date')
    event_type = request.POST.get('event_type', 'other')

    if not all([title, event_date]):
        return JsonResponse({'error': 'Title and date are required.'}, status=400)

    try:
        event = Event.objects.create(
            title=title,
            description=description,
            event_date=event_date,
            event_type=event_type,
            requested_by=(request.user if not request.user.is_staff else None),
            created_by=request.user,
            is_admin_event=request.user.is_staff,
            status=('approved' if request.user.is_staff else 'pending')
        )

        return JsonResponse({'ok': True, 'event': {
            'id': event.id,
            'title': event.title,
            'date': event.event_date.isoformat(),
            'type': 'admin' if event.is_admin_event else 'pending',
        }})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_event_action(request, event_id):
    """Admin actions on tenant events: approve/reject/delete"""
    action = request.POST.get('action')
    event = get_object_or_404(Event, id=event_id)

    if action == 'approve':
        event.status = 'approved'
        event.approved_at = datetime.now()
        event.save()
        Notification.objects.create(
            tenant=event.requested_by,
            title='Event Approved',
            message=f'Your calendar event "{event.title}" has been approved!',
            notification_type='system'
        )
        return JsonResponse({'ok': True, 'status': 'approved'})

    if action == 'reject':
        event.status = 'rejected'
        event.save()
        Notification.objects.create(
            tenant=event.requested_by,
            title='Event Rejected',
            message=f'Your calendar event "{event.title}" has been rejected.',
            notification_type='system'
        )
        return JsonResponse({'ok': True, 'status': 'rejected'})

    if action == 'delete':
        event.delete()
        return JsonResponse({'ok': True, 'deleted': True})

    return JsonResponse({'error': 'Unknown action'}, status=400)


@login_required
@require_http_methods(["POST"])
def api_edit_event(request, event_id):
    """Edit an event. Owner or staff can edit."""
    event = get_object_or_404(Event, id=event_id)
    # Only owner (requested_by) or staff can edit
    if not (request.user.is_staff or (event.requested_by and event.requested_by == request.user)):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    title = request.POST.get('title')
    description = request.POST.get('description')
    event_date = request.POST.get('event_date')
    event_type = request.POST.get('event_type')

    if title:
        event.title = title
    if description is not None:
        event.description = description
    if event_date:
        try:
            event.event_date = event_date
        except Exception:
            return JsonResponse({'error': 'Invalid date'}, status=400)
    if event_type:
        event.event_type = event_type

    event.save()
    return JsonResponse({'ok': True, 'event': {'id': event.id, 'title': event.title, 'date': event.event_date.isoformat()}})


@login_required
@require_http_methods(["POST"])
def api_delete_event(request, event_id):
    """Delete an event. Owner or staff can delete."""
    event = get_object_or_404(Event, id=event_id)
    if not (request.user.is_staff or (event.requested_by and event.requested_by == request.user)):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    event.delete()
    return JsonResponse({'ok': True, 'deleted': True})


@login_required
def request_event(request):
    """Tenant requests to add an event to calendar"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        event_date = request.POST.get('event_date')
        event_type = request.POST.get('event_type', 'other')
        
        if not all([title, event_date]):
            messages.error(request, 'Title and date are required.')
            return redirect('tenant_calendar')
        
        try:
            event = Event.objects.create(
                title=title,
                description=description,
                event_date=event_date,
                event_type=event_type,
                requested_by=request.user,
                created_by=request.user,
                is_admin_event=False,
                status='pending',
            )
            
            # Notify admin
            admin_users = User.objects.filter(is_staff=True)
            for admin in admin_users:
                Notification.objects.create(
                    tenant=admin,
                    title='New Event Request',
                    message=f'{request.user.username} has requested to add "{title}" to calendar.',
                    notification_type='system'
                )
            
            messages.success(request, 'Event request sent to admin for approval!')
        except Exception as e:
            messages.error(request, f'Error requesting event: {e}')
        
        return redirect('tenant_calendar')
    
    return redirect('tenant_calendar')
def password_reset_request(request):
    """Request password reset"""
    if request.method == 'POST':
        username_or_email = request.POST['username_or_email']
        
        # Try to find user by username or email
        user = None
        try:
            if '@' in username_or_email:
                user = User.objects.get(email=username_or_email)
            else:
                user = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            # Don't reveal if user exists or not for security
            messages.success(request, 'If an account exists with that information, a password reset link has been sent.')
            return redirect('password_reset')
        
        # Generate token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build reset link
        reset_link = request.build_absolute_uri(
            f'/password-reset-confirm/{uid}/{token}/'
        )
        
        # Send email
        subject = 'Password Reset - Casa de Liberty'
        message = f"""
Hello {user.username},

You requested to reset your password for Casa de Liberty.

Click the link below to reset your password:
{reset_link}

If you didn't request this, please ignore this email.

This link will expire in 24 hours.

Best regards,
Casa de Liberty Team
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email] if user.email else [],
                fail_silently=False,
            )
            messages.success(request, 'Password reset instructions have been sent to your email.')
        except Exception as e:
            print(f"Email error: {e}")
            messages.info(request, f'Password reset link: {reset_link}')
        
        return redirect('login')
    
    return render(request, 'password_reset.html')

def password_reset_confirm(request, uidb64, token):
    """Confirm password reset with token"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST['password1']
            password2 = request.POST['password2']
            
            if password1 != password2:
                messages.error(request, 'Passwords do not match!')
                return render(request, 'password_reset_confirm.html', {'validlink': True})
            
            if len(password1) < 6:
                messages.error(request, 'Password must be at least 6 characters long!')
                return render(request, 'password_reset_confirm.html', {'validlink': True})
            
            # Set new password
            user.set_password(password1)
            user.save()
            
            messages.success(request, 'Your password has been reset successfully! You can now log in.')
            return redirect('login')
        
        return render(request, 'password_reset_confirm.html', {'validlink': True})
    else:
        messages.error(request, 'This password reset link is invalid or has expired.')
        return render(request, 'password_reset_confirm.html', {'validlink': False})
@login_required
def settings(request):
    """User settings page with password change, profile update, and dark mode"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            # Handle profile update
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            contact_number = request.POST.get('contact_number', '').strip()
            
            # Validate email
            if email and not email.endswith(('.com', '.co', '.edu', '.org', '.net')):
                if '@' not in email:
                    messages.error(request, 'Please enter a valid email address!')
                    return render(request, 'settings.html')
            
            # Update user fields
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save()
            
            # Update or create user profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            if contact_number:
                profile.contact_number = contact_number
                profile.save()
            
            messages.success(request, 'Your profile has been updated successfully!')
            return render(request, 'settings.html')
        
        else:
            # Handle password change (existing code)
            current_password = request.POST.get('current_password')
            new_password1 = request.POST.get('new_password1')
            new_password2 = request.POST.get('new_password2')
            
            # Verify current password
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect!')
                return render(request, 'settings.html')
            
            # Check if new passwords match
            if new_password1 != new_password2:
                messages.error(request, 'New passwords do not match!')
                return render(request, 'settings.html')
            
            # Check password length
            if len(new_password1) < 6:
                messages.error(request, 'Password must be at least 6 characters long!')
                return render(request, 'settings.html')
            
            # Check if new password is different from current
            if current_password == new_password1:
                messages.error(request, 'New password must be different from current password!')
                return render(request, 'settings.html')
            
            # Set new password
            request.user.set_password(new_password1)
            request.user.save()
            
            # Update session to keep user logged in
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Your password has been changed successfully!')
            return render(request, 'settings.html')
    
    return render(request, 'settings.html')

def change_password(request):
    """Change password while logged in"""
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_password1 = request.POST['new_password1']
        new_password2 = request.POST['new_password2']
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect!')
            return render(request, 'change_password.html')
        
        # Check if new passwords match
        if new_password1 != new_password2:
            messages.error(request, 'New passwords do not match!')
            return render(request, 'change_password.html')
        
        # Check password length
        if len(new_password1) < 6:
            messages.error(request, 'Password must be at least 6 characters long!')
            return render(request, 'change_password.html')
        
        # Check if new password is different from current
        if current_password == new_password1:
            messages.error(request, 'New password must be different from current password!')
            return render(request, 'change_password.html')
        
        # Set new password
        request.user.set_password(new_password1)
        request.user.save()
        
        # Update session to keep user logged in
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Your password has been changed successfully!')
        return redirect('dashboard')
    
    return render(request, 'change_password.html')


# ============================================
# UTILITY VIEWS
# ============================================

def open_in_chrome(request):
    """
    API endpoint to open URLs in Chrome browser
    Usage: POST to /api/open-in-chrome/ with JSON: {"url": "https://example.com"}
    """
    import subprocess
    import platform
    from urllib.parse import unquote
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url', '').strip()
            
            # Validate URL
            if not url:
                return JsonResponse({'success': False, 'error': 'No URL provided'})
            
            if not (url.startswith('http://') or url.startswith('https://')):
                url = 'https://' + url
            
            # Decode URL if needed
            url = unquote(url)
            
            # Open in Chrome based on OS
            if platform.system() == 'Windows':
                # Windows: Find Chrome executable
                chrome_paths = [
                    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                    'C:\\Users\\' + platform.node() + '\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe',
                ]
                
                chrome_found = False
                for chrome_path in chrome_paths:
                    try:
                        import os
                        if os.path.exists(chrome_path):
                            subprocess.Popen([chrome_path, url])
                            chrome_found = True
                            break
                    except Exception:
                        continue
                
                if not chrome_found:
                    # Fallback: try using 'start chrome' command
                    try:
                        subprocess.Popen(['cmd', '/c', 'start', 'chrome', url])
                        chrome_found = True
                    except Exception:
                        pass
                
                if chrome_found:
                    return JsonResponse({'success': True, 'message': 'Opening in Chrome...'})
                else:
                    return JsonResponse({'success': False, 'error': 'Chrome not found on system'})
            
            elif platform.system() == 'Darwin':
                # macOS
                subprocess.Popen(['open', '-a', 'Google Chrome', url])
                return JsonResponse({'success': True, 'message': 'Opening in Chrome...'})
            
            elif platform.system() == 'Linux':
                # Linux
                subprocess.Popen(['google-chrome', url])
                return JsonResponse({'success': True, 'message': 'Opening in Chrome...'})
            
            else:
                return JsonResponse({'success': False, 'error': 'Unsupported OS'})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST request required'})


# --------------------------------------------
# Photo management APIs (restored to original Feb 24 behavior)
# --------------------------------------------

@login_required
@require_http_methods(["POST"])
def upload_apartment_photos(request):
    """Handle AJAX upload of apartment photos (staff only)"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    apartment_id = request.POST.get('apartment_id') or request.POST.get('apt_id')
    try:
        apartment = Apartment.objects.get(id=apartment_id)
    except (Apartment.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Apartment not found'}, status=404)

    # Accept either list uploads, individually keyed uploads (photo_0...), or URLs.
    files = request.FILES.getlist('photos') or request.FILES.getlist('initial_photos')
    if not files:
        files = list(request.FILES.values())

    raw_photo_url_values = [
        request.POST.get('photo_urls', ''),
        request.POST.get('initial_photo_urls', ''),
        request.POST.get('photo_url', ''),
    ]
    raw_photo_url_values.extend(
        value for key, value in request.POST.items() if key.startswith('photo_url_')
    )

    created = []
    next_order = apartment.photos.count()

    for photo_url in _normalized_photo_urls(raw_photo_url_values):
        if next_order >= 4:
            break
        photo = ApartmentPhoto.objects.create(
            apartment=apartment,
            photo_url=photo_url,
            photo_order=next_order
        )
        created.append(photo.id)
        next_order += 1

    for f in files:
        if next_order >= 4:
            break
        photo = ApartmentPhoto.objects.create(apartment=apartment, photo=f, photo_order=next_order)
        created.append(photo.id)
        next_order += 1

    return JsonResponse({'success': True, 'created': created})


@login_required
@require_http_methods(["POST"])
def delete_apartment_photo(request, photo_id):
    """AJAX endpoint to remove a previously uploaded apartment photo"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    try:
        photo = ApartmentPhoto.objects.get(id=photo_id)
        photo.delete()
        return JsonResponse({'success': True})
    except ApartmentPhoto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Photo not found'}, status=404)
