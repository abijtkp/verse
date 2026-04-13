from django.db import models
from django.conf import settings   # better than direct import

# userprofile/models.py

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return self.user.email

class Address(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,   #  important change
        on_delete=models.CASCADE,
        related_name='addresses'
    )

    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)

    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default='home')
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)   #  added
    updated_at = models.DateTimeField(auto_now=True)       # added

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.state}"

    class Meta:
        db_table = 'addresses'
        ordering = ['-created_at']   #  optional but useful