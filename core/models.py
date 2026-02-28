from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from datetime import timedelta, datetime
import random
import string

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile - {self.user.username}"


class OTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='otp')
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"OTP for {self.user.username} - {'Used' if self.is_used else 'Active'}"
    
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))


class Apartment(models.Model):
    APARTMENT_TYPES = [
        ('studio', 'Studio'),
        ('one_bedroom', '1 Bedroom'),
        ('two_bedroom', '2 Bedroom'),
        ('three_bedroom', '3 Bedroom'),
        ('four_bedroom', '4 Bedroom'),
    ]
    
    unit_number = models.CharField(max_length=10, unique=True)
    apartment_type = models.CharField(max_length=20, choices=APARTMENT_TYPES)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    max_occupants = models.IntegerField()
    description = models.TextField()
    is_available = models.BooleanField(default=True)
    amenities = models.TextField(help_text="Comma-separated amenities")  # List of amenities
    image_url = models.URLField(blank=True, null=True)  # Apartment photo URL
    
    def __str__(self):
        return f"Apartment {self.unit_number} - {self.get_apartment_type_display()}"
    
    def is_available_for_lease(self, move_in_date, move_out_date=None):
        """Check if apartment is available for given lease period - prevents double booking"""
        if not self.is_available:
            return False
        
        # Check for overlapping leases
        if move_out_date:
            overlapping_leases = Lease.objects.filter(
                apartment=self,
                status__in=['active', 'pending'],
                move_in_date__lt=move_out_date,
                move_out_date__gt=move_in_date
            )
        else:
            # For ongoing leases, just check if any active lease exists
            overlapping_leases = Lease.objects.filter(
                apartment=self,
                status__in=['active', 'pending'],
                move_out_date__isnull=True
            )
        
        return not overlapping_leases.exists()
    
    def get_occupied_dates(self):
        """Get all dates when apartment is leased - used for calendar display"""
        leases = Lease.objects.filter(
            apartment=self,
            status__in=['active', 'pending']
        )
        
        occupied_dates = []
        for lease in leases:
            if lease.move_out_date:
                current = lease.move_in_date
                while current < lease.move_out_date:
                    occupied_dates.append(current.strftime('%Y-%m-%d'))
                    current += timedelta(days=1)
        
        return occupied_dates


class ApartmentPhoto(models.Model):
    """Stores multiple photos for apartment - up to 4 photos per apartment"""
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='photos')  # Which apartment
    photo_url = models.URLField(blank=True, null=True)  # Feb 24 behavior: external image URL
    photo = models.ImageField(upload_to='apartment_photos/', null=True, blank=True)  # Photo file upload
    photo_order = models.IntegerField(default=0, help_text="Order of photo (0-3)")  # Display order
    caption = models.CharField(max_length=255, blank=True, null=True)  # Optional photo description
    created_at = models.DateTimeField(auto_now_add=True)  # When added
    
    class Meta:
        ordering = ['photo_order']  # Display in order
        unique_together = ['apartment', 'photo_order']  # One photo per order slot
    
    def __str__(self):
        return f"Photo {self.photo_order} - Apartment {self.apartment.unit_number}"

    @property
    def display_url(self):
        """Template-safe image URL supporting both URL and uploaded-file sources."""
        if self.photo_url:
            return self.photo_url
        if self.photo:
            try:
                return self.photo.url
            except Exception:
                return ''
        return ''


# ============================================
# LEASE MANAGEMENT
# ============================================

class Lease(models.Model):
    """Represents a lease agreement between tenant and apartment with payment tracking"""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active Lease'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Lease Ended'),
    ]
    
    LEASE_TYPES = [
        ('fixed_term', 'Fixed Term Lease'),
        ('month_to_month', 'Month-to-Month Lease'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(User, on_delete=models.CASCADE)  # Tenant signing lease
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)  # Which apartment
    
    # Lease details
    move_in_date = models.DateField()  # When tenant moves in
    move_out_date = models.DateField(null=True, blank=True, help_text="Leave blank for ongoing lease")  # When tenant moves out
    num_occupants = models.IntegerField()  # Number of people living in unit
    total_lease_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total cost for the lease period")  # Total price for entire lease
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Monthly rent amount")  # Monthly payment amount
    lease_type = models.CharField(max_length=20, choices=LEASE_TYPES, default='fixed_term', help_text="Type of lease")  # Fixed or month-to-month
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')  # Current lease status
    special_requests = models.TextField(blank=True, null=True)  # Any special tenant requests
    rent_due_day = models.IntegerField(null=True, blank=True, help_text="Day of month when rent is due (1-31)")  # Rent due date
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        lease_type = self.get_lease_type_display()
        return f"Lease #{self.id} - {self.tenant.username} - Apt {self.apartment.unit_number} ({lease_type})"
    
    def calculate_lease_months(self):
        """Calculate total months in lease duration"""
        if self.move_out_date:
            months = (self.move_out_date.year - self.move_in_date.year) * 12 + (self.move_out_date.month - self.move_in_date.month)
            if self.move_out_date.day < self.move_in_date.day:
                months -= 1
            return max(months, 0)
        return None
    
    def get_total_paid(self):
        """Get total rent paid by summing all approved payments"""
        return sum(payment.amount for payment in self.payments.filter(payment_status='paid'))
    
    def get_total_paid_rent(self):
        """Get total rent payments using database aggregation (for real-time updates)"""
        return self.payments.filter(payment_status='paid').aggregate(total=Sum('amount'))['total'] or 0
    
    def get_balance(self):
        """Calculate remaining balance owed on lease"""
        return self.total_lease_price - self.get_total_paid()
    
    def get_outstanding_balance(self):
        """Alias for get_balance() - returns amount still owed"""
        return self.get_balance()
    
    def is_fully_paid(self):
        """Check if lease is completely paid"""
        return self.get_balance() <= 0
    
    def is_month_to_month(self):
        """Check if this is a month-to-month lease"""
        return self.lease_type == 'month_to_month'


# ============================================
# PAYMENT MANAGEMENT
# ============================================

class RentPayment(models.Model):
    """Tracks individual rent payments from tenants with status and method"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('gcash', 'GCash'),
        ('card', 'Credit/Debit Card'),
        ('bank', 'Bank Transfer'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('refunded', 'Refunded'),
    ]
    
    # Relationship and payment info
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='payments')  # Which lease this payment belongs to
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Amount paid
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)  # How it was paid
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')  # Payment status
    transaction_id = models.CharField(max_length=100, blank=True, null=True)  # Transaction reference
    payment_date = models.DateTimeField(auto_now_add=True)  # When payment was made
    notes = models.TextField(blank=True, null=True)  # Any additional notes
    
    def __str__(self):
        return f"Rent Payment #{self.id} - Lease #{self.lease.id} - ₱{self.amount}"


# ============================================
# NOTIFICATION SYSTEM
# ============================================

class Notification(models.Model):
    """Stores notifications for users - lease updates, payments, system alerts"""
    NOTIFICATION_TYPES = (
        ('lease', 'Lease'),
        ('payment', 'Payment'),
        ('system', 'System'),
    )

    # Relationship and content
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')  # Recipient
    title = models.CharField(max_length=255)  # Notification title
    message = models.TextField()  # Full message content
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)  # Type of notification
    is_read = models.BooleanField(default=False)  # Whether user has read it
    created_at = models.DateTimeField(auto_now_add=True)  # When created

    def __str__(self):
        return f"{self.title} - {self.tenant.username}"


# ============================================
# MAINTENANCE MANAGEMENT
# ============================================

class Maintenance(models.Model):
    """Tracks maintenance requests from tenants - repairs, cleaning, etc."""
    MAINTENANCE_TYPES = [
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('hvac', 'HVAC/Cooling'),
        ('appliance', 'Appliance'),
        ('cleaning', 'Cleaning'),
        ('furniture', 'Furniture/Fixture'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Relationships and details
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='maintenance_requests')  # Who requested it
    lease = models.ForeignKey(Lease, on_delete=models.SET_NULL, null=True, blank=True)  # Associated lease
    apartment = models.ForeignKey(Apartment, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_requests')  # Which unit
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)  # Type of repair
    description = models.TextField()  # Details of the issue
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')  # Current status
    priority = models.CharField(max_length=10, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium')  # Urgency level
    created_at = models.DateTimeField(auto_now_add=True)  # When requested
    completed_at = models.DateTimeField(null=True, blank=True)  # When completed
    notes = models.TextField(blank=True, null=True)  # Staff notes
    is_cleared = models.BooleanField(default=False, help_text="When cleared, hidden from view but remains in database")  # Soft delete flag
    
    class Meta:
        ordering = ['created_at']  # FIFO - oldest first
    
    def __str__(self):
        apt_info = f"Apt {self.apartment.unit_number}" if self.apartment else "No Apartment"
        return f"Maintenance #{self.id} - {self.get_maintenance_type_display()} - {apt_info}"


# ============================================
# CALENDAR/EVENT MANAGEMENT
# ============================================

class Event(models.Model):
    """Calendar events for property management - tenant bookings, admin events, etc."""
    EVENT_TYPES = [
        ('admin', 'Admin Event'),
        ('maintenance', 'Maintenance'),
        ('holiday', 'Holiday'),
        ('inspection', 'Inspection'),
        ('other', 'Other'),
    ]
    
    EVENT_STATUS = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # Event details
    title = models.CharField(max_length=255)  # Event name
    description = models.TextField(blank=True, null=True)  # Event description
    event_date = models.DateField()  # When the event is
    event_time = models.TimeField(blank=True, null=True)  # What time
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='other')  # Type of event
    
    # Relationships
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events_created')  # Who created it
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_requests')  # Who requested it (if tenant)
    apartment = models.ForeignKey(Apartment, on_delete=models.SET_NULL, null=True, blank=True)  # Which apartment
    
    # Status and approval
    status = models.CharField(max_length=20, choices=EVENT_STATUS, default='approved')  # Approval status
    is_admin_event = models.BooleanField(default=False, help_text="True if created by admin, False if tenant request")  # Who created it
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)  # When created
    approved_at = models.DateTimeField(null=True, blank=True)  # When approved
    color = models.CharField(max_length=20, default='#667eea', help_text="Color for calendar display")  # Calendar color
    
    class Meta:
        ordering = ['event_date', 'event_time']
        unique_together = ['event_date', 'title', 'created_by']
    
    def __str__(self):
        return f"{self.title} - {self.event_date} ({self.get_event_type_display()})"


# ============================================
# RENT TRACKING
# ============================================

class RentDueDate(models.Model):
    """Track when rent is due for each tenant - used for payment reminders"""
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rent_dues')  # Which tenant
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='due_dates')  # Which lease
    due_date = models.DateField()  # When payment is due
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)  # How much is due
    is_paid = models.BooleanField(default=False)  # Payment status
    is_recurring_monthly = models.BooleanField(default=True, help_text="If True, this rent recurs monthly")  # Monthly or one-time
    created_at = models.DateTimeField(auto_now_add=True)  # When created
    
    class Meta:
        ordering = ['due_date']
    
    def __str__(self):
        return f"Rent due {self.due_date} - {self.tenant.username} - ₱{self.amount_due}"


# ============================================
# TIME OFF / ADMIN AVAILABILITY
# ============================================

class TimeOff(models.Model):
    """Track admin/staff days off for scheduling"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_off_periods')  # Staff member
    start_date = models.DateField()  # Start of time off
    end_date = models.DateField()  # End of time off
    reason = models.CharField(max_length=255, blank=True)  # Why they're off (vacation, sick, etc)
    created_at = models.DateTimeField(auto_now_add=True)  # When created
    
    class Meta:
        ordering = ['start_date']
    
    def __str__(self):
        return f"{self.user.username} - Off from {self.start_date} to {self.end_date}"
