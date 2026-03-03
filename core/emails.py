import logging

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _is_smtp_backend():
    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    return 'smtp' in backend


def _email_backend_configured():
    """Return True if email backend appears configured enough for OTP delivery."""
    if not _is_smtp_backend():
        # Console/file/locmem backends are valid in local development.
        return True

    host_user = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()
    host_password = (getattr(settings, 'EMAIL_HOST_PASSWORD', '') or '').strip()
    placeholder_values = {'', 'your-email@gmail.com'}
    if host_user in placeholder_values or not host_password:
        return False
    return True


def _send_email(subject, message, recipients):
    """Central email sender with timeout + config checks for safer OTP flows."""
    if not recipients:
        return False

    if not _email_backend_configured():
        logger.warning('Email backend not configured. Cannot send email to recipients=%s', recipients)
        return False

    timeout = int(getattr(settings, 'EMAIL_TIMEOUT', 10) or 10)
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()
    if not from_email or from_email == 'your-email@gmail.com':
        from_email = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()

    try:
        connection = get_connection(fail_silently=False, timeout=timeout)
        send_mail(
            subject,
            message,
            from_email,
            recipients,
            fail_silently=False,
            connection=connection,
        )
        return True
    except Exception:
        logger.exception('Failed sending email. subject=%s recipients=%s', subject, recipients)
        return False

def send_lease_confirmation_email(lease):
    """Send email to tenant when admin approves their lease application
    
    Includes: Lease ID, apartment details, dates, total price
    Triggered: When lease status changes from pending→active
    """
    subject = f'Lease Confirmation - Casa de Liberty #{lease.id}'
    
    message = f"""
    Dear {lease.tenant.username},

    Your lease has been confirmed!

    Lease Details:
    ----------------
    Lease ID: #{lease.id}
    Apartment: {lease.apartment.unit_number} ({lease.apartment.get_apartment_type_display()})
    Move-in: {lease.move_in_date}
    Move-out: {lease.move_out_date}
    Lease Type: {lease.get_lease_type_display()}
    Number of Occupants: {lease.num_occupants}
    Total Lease Price: ₱{lease.total_lease_price}

    We look forward to welcoming you to Casa de Liberty!

    Best regards,
    Casa de Liberty Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [lease.tenant.email],
        fail_silently=False,
    )

def send_rent_payment_confirmation_email(payment):
    """Send email to tenant when they submit a rent payment
    
    Includes: Payment receipt, lease summary, remaining balance
    Triggered: When add_payment() successfully creates RentPayment record
    """
    lease = payment.lease
    subject = f'Rent Payment Received - Casa de Liberty Lease #{lease.id}'
    
    message = f"""
    Dear {lease.tenant.username},

    We have received your rent payment!

    Payment Details:
    ----------------
    Payment ID: #{payment.id}
    Lease ID: #{lease.id}
    Amount Paid: ₱{payment.amount}
    Payment Method: {payment.get_payment_method_display()}
    Payment Date: {payment.payment_date.strftime('%B %d, %Y %I:%M %p')}
    
    Lease Summary:
    ----------------
    Total Lease Price: ₱{lease.total_lease_price}
    Total Paid: ₱{lease.get_total_paid()}
    Remaining Balance: ₱{lease.get_balance()}

    Thank you for your payment!

    Best regards,
    Casa de Liberty Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [lease.tenant.email],
        fail_silently=False,
    )

def send_lease_cancellation_email(lease):
    """Send email to tenant when their lease is cancelled
    
    Includes: Cancelled lease details
    Triggered: When lease status changed to 'cancelled'
    """
    subject = f'Lease Cancelled - Casa de Liberty #{lease.id}'
    
    message = f"""
    Dear {lease.tenant.username},

    Your lease has been cancelled.

    Cancelled Lease Details:
    --------------------------
    Lease ID: #{lease.id}
    Apartment: {lease.apartment.unit_number}
    Move-in: {lease.move_in_date}
    Move-out: {lease.move_out_date}
    Total Lease Price: ₱{lease.total_lease_price}

    If you have any questions, please contact us.

    Best regards,
    Casa de Liberty Team
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [lease.tenant.email],
        fail_silently=False,
    )

def send_admin_notification(subject, message):
    """Send notification to admin"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMIN_EMAIL],
        fail_silently=False,
    )

def send_otp_email(user, otp_code):
    """Send OTP to user's email for password change verification
    
    Includes: 6-digit OTP, expiration time (10 minutes)
    Triggered: When user initiates password change
    """
    subject = 'Casa de Liberty - Password Change OTP'
    
    message = f"""
Dear {user.first_name or user.username},

You have requested to change your password at Casa de Liberty.

Your One-Time Password (OTP) is: {otp_code}

IMPORTANT:
- This OTP will expire in 10 minutes
- Never share this OTP with anyone
- If you did not request this, please ignore this email

To confirm your password change, please use this OTP in the password change form.

Best regards,
Casa de Liberty Team
    """
    
    if not getattr(user, 'email', ''):
        return False

    return _send_email(subject, message, [user.email])

def send_password_reset_otp_email(user, otp_code):
    """Send OTP to user's email for password reset verification
    
    Includes: 6-digit OTP, expiration time (10 minutes)
    Triggered: When user requests to reset forgotten password
    """
    subject = 'Casa de Liberty - Password Reset OTP'
    
    message = f"""
Dear {user.first_name or user.username},

You have requested to reset your password at Casa de Liberty.

Your One-Time Password (OTP) is: {otp_code}

IMPORTANT:
- This OTP will expire in 10 minutes
- Never share this OTP with anyone
- If you did not request this, please ignore this email and your password will remain unchanged

To reset your password, please use this OTP on the password reset page.

Best regards,
Casa de Liberty Team
    """
    
    if not getattr(user, 'email', ''):
        return False

    return _send_email(subject, message, [user.email])


def send_password_reset_link_email(user, reset_link):
    """Send password reset link email with robust error handling."""
    if not getattr(user, 'email', ''):
        return False

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

    return _send_email(subject, message, [user.email])

# Backwards compatibility aliases
send_booking_confirmation_email = send_lease_confirmation_email
send_payment_confirmation_email = send_rent_payment_confirmation_email
send_cancellation_email = send_lease_cancellation_email
