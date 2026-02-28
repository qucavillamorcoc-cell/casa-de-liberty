import re

# Read the settings file
with open('config/settings.py', 'r') as f:
    content = f.read()

# Find and replace the email configuration section
old_pattern = r"# Email Configuration\nEMAIL_BACKEND = 'django\.core\.mail\.backends\.console\.EmailBackend'.*?ADMIN_EMAIL = 'admin@casadeliberty\.com'"

new_text = """# Email Configuration
# Using Gmail SMTP to send real emails to users
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
# IMPORTANT: Use Gmail App Password, NOT your regular Gmail password
# Generate app password at: https://myaccount.google.com/apppasswords
# Steps: 1. Enable 2-Factor Authentication on your Google account
#        2. Go to https://myaccount.google.com/apppasswords
#        3. Select "Mail" and "Windows Computer"
#        4. Copy the 16-character password and paste it below
EMAIL_HOST_USER = 'your-email@gmail.com'  # Change this to your Gmail address
EMAIL_HOST_PASSWORD = 'your-16-char-app-password'  # Change this to your app password

DEFAULT_FROM_EMAIL = 'your-email@gmail.com'  # Should match EMAIL_HOST_USER
ADMIN_EMAIL = 'admin@casadeliberty.com'"""

content = re.sub(old_pattern, new_text, content, flags=re.DOTALL)

# Write back the settings file
with open('config/settings.py', 'w') as f:
    f.write(content)

print("✓ Email configuration updated to Gmail SMTP")
print("\n📧 Next steps:")
print("1. Go to https://myaccount.google.com/apppasswords")
print("2. Enable 2-Factor Authentication if not already enabled")
print("3. Select 'Mail' and 'Windows Computer'")
print("4. Copy the 16-character app password")
print("5. Update config/settings.py:")
print("   - Change EMAIL_HOST_USER to your Gmail address")
print("   - Change EMAIL_HOST_PASSWORD to your 16-char app password")
