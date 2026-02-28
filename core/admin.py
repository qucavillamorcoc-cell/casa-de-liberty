from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Apartment, ApartmentPhoto, Lease, RentPayment, Event, RentDueDate, TimeOff, UserProfile

class ApartmentPhotoInline(admin.TabularInline):
    """Inline admin for managing apartment photos directly from apartment page"""
    model = ApartmentPhoto
    extra = 1
    fields = ['photo_url', 'photo', 'photo_order', 'caption']
    ordering = ['photo_order']
    
    class Media:
        css = {'all': ('css/admin.css',)}

@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ['unit_number', 'apartment_type', 'monthly_rent', 'is_available', 'photo_count']
    list_filter = ['apartment_type', 'is_available']
    search_fields = ['unit_number']
    inlines = [ApartmentPhotoInline]
    
    def photo_count(self, obj):
        """Display count of photos for this apartment"""
        return obj.photos.count()
    photo_count.short_description = 'Photos'
    
    class Media:
        css = {'all': ('css/admin.css',)}

@admin.register(ApartmentPhoto)
class ApartmentPhotoAdmin(admin.ModelAdmin):
    """Admin for managing apartment photos"""
    list_display = ['apartment', 'photo_order', 'caption', 'created_at']
    list_filter = ['apartment', 'photo_order', 'created_at']
    search_fields = ['apartment__unit_number', 'caption']
    fieldsets = (
        ('Photo Information', {
            'fields': ('apartment', 'photo_url', 'photo', 'photo_order')
        }),
        ('Details', {
            'fields': ('caption',),
            'classes': ('collapse',)
        }),
    )
    
    class Media:
        css = {'all': ('css/admin.css',)}

@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'tenant', 'apartment', 'lease_type', 'move_in_date', 'move_out_date', 'status', 'total_lease_price']
    list_filter = ['status', 'lease_type', 'move_in_date']
    search_fields = ['tenant__username', 'apartment__unit_number']
    fieldsets = (
        ('Lease Information', {
            'fields': ('tenant', 'apartment', 'lease_type', 'status')
        }),
        ('Dates', {
            'fields': ('move_in_date', 'move_out_date')
        }),
        ('Pricing', {
            'fields': ('total_lease_price', 'monthly_rent')
        }),
        ('Occupancy & Requests', {
            'fields': ('num_occupants', 'special_requests')
        }),
        ('Rent Due Settings', {
            'fields': ('rent_due_day',),
            'description': 'Set the day of month when rent is due (1-31)',
            'classes': ('collapse',)
        }),
    )

@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'lease', 'amount', 'payment_method', 'payment_status', 'payment_date']
    list_filter = ['payment_status', 'payment_method', 'payment_date']
    search_fields = ['lease__id', 'transaction_id']

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_date', 'event_type', 'status', 'created_by', 'is_admin_event']
    list_filter = ['event_type', 'status', 'event_date', 'is_admin_event']
    search_fields = ['title', 'created_by__username', 'requested_by__username']
    readonly_fields = ['created_at', 'approved_at']

@admin.register(RentDueDate)
class RentDueDateAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'due_date', 'amount_due', 'is_paid', 'is_recurring_monthly']
    list_filter = ['due_date', 'is_paid', 'is_recurring_monthly']
    search_fields = ['tenant__username']
    fieldsets = (
        ('Payment Information', {
            'fields': ('tenant', 'booking', 'due_date', 'amount_due')
        }),
        ('Payment Status', {
            'fields': ('is_paid',)
        }),
        ('Recurring Settings', {
            'fields': ('is_recurring_monthly',),
            'description': 'If enabled, this payment will show as a monthly reminder on the calendar for 12 months'
        }),
    )

@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_date', 'end_date', 'reason']
    list_filter = ['start_date', 'user']
    search_fields = ['user__username', 'reason']
# Custom User Admin to display phone number
class CustomUserAdmin(BaseUserAdmin):
    """Extended User admin to show phone number from UserProfile"""
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_phone_number', 'is_staff']
    
    def get_phone_number(self, obj):
        """Retrieve phone number from related UserProfile"""
        try:
            return obj.profile.contact_number or 'N/A'
        except UserProfile.DoesNotExist:
            return 'N/A'
    get_phone_number.short_description = 'Phone Number'

# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
