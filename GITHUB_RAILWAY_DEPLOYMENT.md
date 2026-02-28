# GitHub & Railway Deployment Guide

## Step 1: Push to GitHub

### 1.1 Create a GitHub Repository
1. Go to [github.com](https://github.com) and sign in
2. Click **New** (top left) or go to [github.com/new](https://github.com/new)
3. **Repository name**: `casa-de-liberty`
4. **Description**: Casa de Liberty Property Management System
5. **Public** (so Railway can deploy it)
6. **DO NOT** initialize README, .gitignore, or license (we have them locally)
7. Click **Create repository**

### 1.2 Push to GitHub
Copy the commands from GitHub's "Push an existing repository" section (adjust your username):

```powershell
cd c:\Users\admin\OneDrive\Documents\casa_de_liberty

# Remove 'origin' if it exists (shouldn't be needed)
git remote remove origin

# Add your GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/casa-de-liberty.git

# Stage all files
git add .

# First commit
git commit -m "Initial commit: Casa de Liberty property management system"

# Push to main branch
git branch -M main
git push -u origin main
```

**Replace `YOUR_USERNAME` with your actual GitHub username.**

---

## Step 2: Deploy to Railway

### 2.1 Connect Railway to GitHub
1. Go to [railway.app](https://railway.app)
2. Sign up/log in with GitHub
3. Click **New Project** → **Deploy from GitHub repo**
4. **Authorize Railway** (if prompted)
5. Select your **casa-de-liberty** repository
6. Click **Deploy Now**

Railway will automatically:
- Detect `Procfile` and `runtime.txt`
- Install dependencies from `requirements.txt`
- Run migrations
- Start the application with gunicorn

### 2.2 Configure Environment Variables
Once Railway is deploying:

1. Go to your Railway project dashboard
2. Click the service (your app)
3. Click **Variables** tab
4. Add these critical variables:

```
DATABASE_URL=postgresql://... (Railway generates this)
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-railway-domain.railway.app
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
SECURE_SSL_REDIRECT=True
```

**For SECRET_KEY**, generate one:
```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2.3 Configure PostgreSQL (Recommended)
For production, use PostgreSQL instead of SQLite:

1. In Rails project, click **+ Add**
2. Select **PostgreSQL**
3. Railway auto-creates `DATABASE_URL` variable
4. Update `requirements.txt` to include `psycopg2-binary`:

```
psycopg2-binary==2.9.9
```

Then push to GitHub:
```powershell
git add requirements.txt
git commit -m "Add psycopg2 for PostgreSQL"
git push
```

---

## Step 3: First Deployment Checklist

✅ **Before pushing:**
- [ ] `.env` file is in `.gitignore` (sensitive data not exposed)
- [ ] `db.sqlite3` is in `.gitignore`
- [ ] `DEBUG=False` in production settings
- [ ] All environment variables are set in Railway
- [ ] Email credentials are correct
- [ ] Database URL is configured

**What's included:**
- `Procfile` — tells Railway how to run the app
- `runtime.txt` — specifies Python version
- `requirements.txt` — all dependencies (including gunicorn)
- `.gitignore` — excludes sensitive files

---

## Step 4: Troubleshooting

### App won't start?
Check Railway's **Logs** tab to see error messages.

### Database migration errors?
Railway runs `python manage.py migrate` automatically from the Procfile. If it fails:
1. Check you have `psycopg2-binary` in requirements.txt (for PostgreSQL)
2. Check DATABASE_URL environment variable is set
3. Review logs for specific errors

### Static files not loading?
Already handled by **WhiteNoise** (in requirements.txt). Django static files are collected automatically during deployment.

### Email not sending?
Check in Railway variables:
- EMAIL_HOST_USER = your Gmail address
- EMAIL_HOST_PASSWORD = your **App Password** (not regular password)

[Generate Gmail App Password](https://myaccount.google.com/apppasswords)

---

## Step 5: Updates & Redeployment

Every time you make changes:

```powershell
git add .
git commit -m "Your change description"
git push origin main
```

Railway automatically redeploys when it detects a push to main branch.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `git add .` | Stage all changes |
| `git commit -m "message"` | Create commit |
| `git push origin main` | Push to GitHub (auto-deploys) |
| `git log` | View commit history |
| `git status` | See current changes |

---

## File Structure for Deployment

```
casa-de-liberty/
├── Procfile                 ← Railway process file
├── runtime.txt              ← Python version
├── requirements.txt         ← Dependencies (includes gunicorn)
├── .gitignore              ← Excludes db, .env, etc
├── manage.py
├── config/
│   ├── settings.py         ← Update ALLOWED_HOSTS for Railway
│   ├── wsgi.py
│   └── urls.py
├── core/                   ← Your Django app
├── templates/
├── static/
└── media/
```

---

## Success Indicators

✅ **Green checkmark** on Railway dashboard = app is running
✅ **Your domain URL works** = deployment successful
✅ **Email sends** = configured properly
✅ **Database works** = migrations ran successfully

---

## Support

- Railway Docs: https://docs.railway.app
- Django Deployment: https://docs.djangoproject.com/en/stable/howto/deployment/
- GitHub Docs: https://docs.github.com
