#!/usr/bin/env python
"""Setup Gmail SMTP configuration for Django"""

with open('config/settings.py', 'r') as f:
    lines = f.readlines()

# Find the line to start replacing
for i, line in enumerate(lines):
    if 'EMAIL_BACKEND' in line and 'console' in line:
        # Replace from this line onwards
        new_lines = lines[:i] + [
            '# Email Configuration\n',
            '# Using Gmail SMTP to send real emails to users\n',
            "EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'\n",
            "EMAIL_HOST = 'smtp.gmail.com'\n",
            'EMAIL_PORT = 587\n',
            'EMAIL_USE_TLS = True\n',
            '# IMPORTANT: Use Gmail App Password, NOT your regular Gmail password\n',
            '# Generate app password at: https://myaccount.google.com/apppasswords\n',
            '# Steps: 1. Enable 2-Factor Authentication on your Google account\n',
            '#        2. Go to https://myaccount.google.com/apppasswords\n',
            '#        3. Select "Mail" and "Windows Computer"\n',
            '#        4. Copy the 16-character password and paste it below\n',
            "EMAIL_HOST_USER = 'your-email@gmail.com'  # Change this to your Gmail address\n",
            "EMAIL_HOST_PASSWORD = 'your-16-char-app-password'  # Change this to your app password\n",
            "\n",
            "DEFAULT_FROM_EMAIL = 'your-email@gmail.com'  # Should match EMAIL_HOST_USER\n",
            "ADMIN_EMAIL = 'admin@casadeliberty.com'\n"
        ]
        # Skip old lines until ADMIN_EMAIL
        for j in range(i, len(lines)):
            if 'ADMIN_EMAIL' in lines[j]:
                new_lines += lines[j+1:]
                break
        break

with open('config/settings.py', 'w') as f:
    f.writelines(new_lines)

print('✓ Gmail SMTP configuration applied successfully!')
print('\n📧 Next steps:')
print('1. Go to https://myaccount.google.com/apppasswords')
print('2. Enable 2-Factor Authentication if not already enabled')
print('3. Select "Mail" and "Windows Computer"')
print('4. Copy the 16-character app password')
print('5. Update config/settings.py:')
print('   - Change EMAIL_HOST_USER to your Gmail address')
print('   - Change EMAIL_HOST_PASSWORD to your 16-char app password')
