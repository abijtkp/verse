<div align="center">

# 👟 VERSE — Premium Shoe E-Commerce Platform

**A fully-featured, production-ready Django e-commerce application for footwear retail.**

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Razorpay](https://img.shields.io/badge/Razorpay-02042B?style=for-the-badge&logo=razorpay&logoColor=white)](https://razorpay.com)
[![Cloudinary](https://img.shields.io/badge/Cloudinary-3448C5?style=for-the-badge&logo=cloudinary&logoColor=white)](https://cloudinary.com)

</div>

---

## 📖 Project Overview

**VERSE** is a full-stack e-commerce platform built with Django, designed to sell premium footwear. It offers a complete shopping experience for customers and a powerful management interface for administrators. The platform handles the entire order lifecycle — from product browsing and cart management to payment processing and return resolution — with a focus on security, reliability, and clean code.

---

## ✨ Key Highlights

- 🔐 **OTP-based email verification** with resend throttling
- 🌐 **Google OAuth 2.0** social login via `django-allauth`
- 🛍️ **Full shopping flow** — browse, wishlist, cart, checkout, pay, review
- 💳 **Razorpay** integration for online payments and wallet top-ups
- 👜 **Built-in digital Wallet** with full transaction history
- 🎟️ **Coupon & Offer engine** with percentage and flat discount support
- 📣 **Referral system** with unique referral codes per user
- 📦 **Individual item-level** cancellation and return management
- 🧾 **PDF invoice** generation per order using `xhtml2pdf`
- 📊 **Admin sales reports** with Excel and PDF export
- ☁️ **Cloudinary** media storage + **Whitenoise** for static files
- 📝 **Structured logging** across all critical modules
- 📱 Fully responsive design with mobile-first navigation
- ✨ Glassmorphism-inspired mobile navigation and account sidebar

---

## 👤 User Features

### Authentication & Account
| Feature | Details |
|---|---|
| **Registration** | Email + Full name + Password with strong password validation |
| **OTP Verification** | 6-digit OTP sent via email at signup; resend with 30-second throttle |
| **Login** | Email/password with blocked-user and unverified-account checks |
| **Google Login** | OAuth 2.0 via `django-allauth`; custom adapter for account linking |
| **Forgot Password** | OTP-based password reset flow |
| **Change Email** | OTP sent to new email before updating; blocked for Google accounts |
| **Change Password** | In-profile password change using Django's `PasswordChangeForm` |
| **Referral Codes** | Auto-generated `VERSE<uuid8>` code per user; referrer tracked on signup |

### Profile & Addresses
- View and edit profile (full name, phone, bio, date of birth)
- Upload / remove profile photo (JPEG, PNG, WEBP; max 2 MB)
- Manage multiple saved addresses (Home / Work / Other)
- Set default address; auto-promotes next address when default is deleted
- Duplicate address detection

### Product Browsing
- **Product listing** with pagination (8 per page)
- **Search** by product name, description, color, or size
- **Filters** — category, size, color, price range
- **Sort** — name A–Z / Z–A, price low–high / high–low
- **Product detail** — color swatch selection, size picker, related products
- Real-time offer price display (best offer per product)

### Cart & Wishlist
- Add to cart with stock and max-quantity (5) enforcement
- Increase / decrease / remove items with AJAX updates
- Wishlist — add, remove, and toggle with AJAX; items auto-removed when added to cart
- **Buy Now** — single-click direct checkout from product detail page
- Cart count displayed live in the navigation bar (context processor)

### Checkout & Orders
- Address selection at checkout (or add a new address inline)
- Coupon apply/remove with real-time discount calculation
- Payment methods: **Cash on Delivery**, **Razorpay**, **Wallet**
- COD restricted to orders below a set threshold (handled in order logic)
- **Order success** page with summary
- **My Orders** — full order history with status tracking
- **Order detail** — itemised view with individual item status
- **Cancel entire order** or **cancel individual items** with optional reason
- **Return entire order** or **return individual items** with reason; admin review required
- **Download PDF invoice** for any delivered order

### Reviews
- Star-rating and text review on delivered products
- Only verified purchasers (delivered order items) can submit a review
- One review per user per product; updates on re-submission
- Average rating and review count displayed on product detail

### Wallet
- View current balance and full paginated transaction history
- **Top-up wallet** via Razorpay with signature verification
- Wallet balance cap of ₹50,000
- Wallet used as a payment method at checkout

---

## 🛠️ Admin Features

### Dashboard
- Total revenue (all-time and current month)
- Active orders count
- Total customer count
- Total product count
- Low-stock variants alert (stock ≤ 5)
- Pending return requests count
- Recent orders table
- Top 5 best-selling products with images
- Daily revenue and order trend charts
- Category distribution chart
- Top selling categories by quantity and revenue

### User Management
- List all non-staff users
- **Block / Unblock** user accounts (blocked users are barred from login)

### Category Management
- List, add, edit categories
- Upload category images (served via Cloudinary)
- Toggle active/inactive status (soft-toggle)

### Product & Variant Management
- List, add, edit products with category assignment
- Soft-delete products
- Manage product variants (SKU, size, color, price, stock)
- Add / delete variant images; set primary image per variant
- Soft-delete variants

### Order Management
- List all orders with filtering
- View detailed order page with all items and payment info
- **Update order status** (Pending → Shipped → Out for Delivery → Delivered → Cancelled/Returned)

### Return Management
- View all pending return requests
- **Approve return** — refunds amount to user's wallet automatically
- **Reject return** — provide rejection reason; status updated accordingly

### Coupon Management
- Create coupons with: code, discount type (Percentage / Fixed), discount value, minimum order amount, maximum discount cap, validity dates, and usage limit
- Edit existing coupons
- Toggle active/inactive status
- Delete coupons
- Per-user usage tracking via `CouponUsage` model

### Offer Management
- Create **Product Offers** and **Category Offers**
- Discount types: Percentage or Flat
- Optional maximum discount cap per offer
- Toggle active/inactive; edit; delete
- Best applicable offer is auto-selected per product at cart and checkout time

### Sales Reports
- Filter by: Daily, Weekly, Monthly, Yearly, or Custom date range
- **Metrics**: Total Orders, Total Revenue, Net Revenue, Total Discount, Offer Discount, Coupon Discount, Cancelled Amount, Returned Amount, Products Sold, Average Order Value
- Revenue trend chart (hourly for daily, daily for weekly/monthly, monthly for yearly)
- Paginated order table
- **Export to Excel** (`.xlsx` via `openpyxl`)
- **Export to PDF** (via `xhtml2pdf`)

---

## 🏗️ Tech Stack

| Category | Technology |
|---|---|
| **Backend Framework** | Django 5.2 |
| **Database** | PostgreSQL (`psycopg2-binary`) |
| **Authentication** | Custom email-based auth + `django-allauth` (Google OAuth 2.0) |
| **Payment Gateway** | Razorpay (`razorpay` SDK) |
| **Media Storage** | Cloudinary (`django-cloudinary-storage`) |
| **Static Files** | Whitenoise (`CompressedManifestStaticFilesStorage`) |
| **PDF Generation** | `xhtml2pdf`, `reportlab` |
| **Excel Export** | `openpyxl` |
| **Image Processing** | `Pillow` |
| **Config Management** | `python-decouple` |
| **OTP Delivery** | Django SMTP email backend |
| **Frontend** | HTML, CSS (Vanilla), JavaScript, Tailwind CSS (admin panel) |
| **Logging** | Python `logging` with rotating file handlers |
| **Time Zone** | Asia/Kolkata (IST) |

---

## 📁 Project Structure

```
verse_shoes/
├── accounts/           # Custom user model, OTP, login, signup, password reset
│   ├── adapters.py     # Custom Google OAuth adapter
│   ├── decorators.py   # user_required decorator
│   ├── models.py       # User (AbstractUser), OTP models
│   ├── utils.py        # OTP generation & email sending
│   └── validators.py   # StrongPasswordValidator
├── adminpanel/         # Custom admin interface
│   └── views/
│       ├── core_views.py       # Dashboard, login, logout
│       ├── category_views.py   # Category CRUD
│       ├── product_views.py    # Product CRUD
│       ├── variant_views.py    # Variant & image management
│       ├── user_views.py       # User block/unblock
│       ├── order_views.py      # Order management & returns
│       ├── coupon_views.py     # Coupon CRUD
│       ├── offer_views.py      # Offer CRUD
│       └── report_views.py     # Sales report & exports
├── cart/               # Cart, CartItem, Wishlist models and views
├── coupons/            # Coupon & CouponUsage models and logic
├── offers/             # ProductOffer, CategoryOffer models and utils
├── orders/             # Order, OrderItem models; checkout, invoice, return views
├── payments/           # Payment, Wallet, WalletTransaction models and views
├── products/           # Category, Product, Variant, VariantImage, ProductReview
├── userprofile/        # Profile & Address management
├── verse_shoes/        # Django project settings, root URLs
├── templates/          # All HTML templates (app-level subdirectories)
├── static/             # Static assets (CSS, JS, images)
├── staticfiles/        # Collected static files for production
├── media/              # Local media (dev only; Cloudinary used in production)
├── logs/               # Rotating log files (django.log, errors.log, security.log)
├── requirements.txt
└── .env                # Environment variables (not committed)
```

---

## 🚀 Installation Guide

### Prerequisites
- Python 3.10+
- PostgreSQL
- A Cloudinary account
- A Razorpay account
- A Google Cloud OAuth 2.0 credential

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/verse_shoes.git
cd verse_shoes
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root (see [Environment Variables](#-environment-variables) below).

### 5. Apply Migrations
```bash
python manage.py migrate
```

### 6. Create a Superuser
```bash
python manage.py createsuperuser
```

### 7. Collect Static Files
```bash
python manage.py collectstatic
```

### 8. Run the Development Server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for the storefront and `http://127.0.0.1:8000/adminpanel/` for the custom admin panel.

---

## 🔑 Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Django
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000

# Database (PostgreSQL)
DB_NAME=verse_db
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Email (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Cloudinary
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Razorpay
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxx
RAZORPAY_KEY_SECRET=your-razorpay-secret

# Google OAuth (django-allauth)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# django.contrib.sites
SITE_ID=1
```

> **Note:** For production, set `DEBUG=False` and update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` with your actual domain.


---

## 🔮 Future Improvements

- [ ] Wishlist sharing via unique URL
- [ ] Real-time order tracking with WebSockets
- [ ] Email notifications for order status updates
- [ ] Product variant stock alerts / back-in-stock notifications
- [ ] Advanced analytics (customer lifetime value, cohort analysis)
- [ ] Multi-currency support
- [ ] REST API layer for a future mobile app
- [ ] Unit and integration test suite
- [ ] Homepage marketing carousel sections
- [ ] Product recommendation engine
- [ ] Progressive Web App (PWA) support

---

## 👨‍💻 Author

**Abhijith**


- 🌐 GitHub: https://github.com/abijtkp
- 💼 LinkedIn: https://www.linkedin.com/in/abhijith-k-p-066639245

---

<div align="center">

Built with Django, PostgreSQL, Razorpay, and Cloudinary.

</div>
