from django import forms
from django.contrib.auth.models import User


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        strip=True,
        error_messages={'required': 'Please enter both username and password.'},
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={'required': 'Please enter both username and password.'},
    )


class RegisterForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        strip=True,
        error_messages={'required': 'Username, email, and password are required.'},
    )
    email = forms.EmailField(
        error_messages={
            'required': 'Username, email, and password are required.',
            'invalid': 'Please enter a valid email address.',
        }
    )
    password = forms.CharField(
        min_length=6,
        strip=False,
        widget=forms.PasswordInput,
        error_messages={'required': 'Username, email, and password are required.'},
    )
    contact_number = forms.CharField(max_length=20, required=False, strip=True)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Email is already registered. Please use another email.')
        return email


class PasswordResetRequestForm(forms.Form):
    username_or_email = forms.CharField(
        strip=True,
        error_messages={'required': 'Please enter your username or email address.'},
    )


class PasswordResetConfirmForm(forms.Form):
    password1 = forms.CharField(
        min_length=6,
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please fill in both password fields.',
            'min_length': 'Password must be at least 6 characters long!',
        },
    )
    password2 = forms.CharField(
        min_length=6,
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please fill in both password fields.',
            'min_length': 'Password must be at least 6 characters long!',
        },
    )

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('password1')
        pw2 = cleaned.get('password2')
        if pw1 and pw2 and pw1 != pw2:
            raise forms.ValidationError('Passwords do not match!')
        return cleaned


class ChangePasswordRequestOTPForm(forms.Form):
    current_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput,
        error_messages={'required': 'Please enter your current password.'},
    )


class ChangePasswordVerifyOTPForm(forms.Form):
    otp_code = forms.CharField(
        min_length=6,
        max_length=6,
        strip=True,
        error_messages={
            'required': 'Please enter the OTP code from your email.',
            'min_length': 'OTP must be a 6-digit code.',
            'max_length': 'OTP must be a 6-digit code.',
        },
    )
    new_password1 = forms.CharField(
        min_length=6,
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please fill in both new password fields.',
            'min_length': 'Password must be at least 6 characters long!',
        },
    )
    new_password2 = forms.CharField(
        min_length=6,
        strip=False,
        widget=forms.PasswordInput,
        error_messages={
            'required': 'Please fill in both new password fields.',
            'min_length': 'Password must be at least 6 characters long!',
        },
    )

    def clean_otp_code(self):
        otp_code = self.cleaned_data['otp_code'].strip()
        if not otp_code.isdigit() or len(otp_code) != 6:
            raise forms.ValidationError('OTP must be a 6-digit code.')
        return otp_code

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('new_password1')
        pw2 = cleaned.get('new_password2')
        if pw1 and pw2 and pw1 != pw2:
            raise forms.ValidationError('New passwords do not match!')
        return cleaned
