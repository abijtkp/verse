from django.db import models


from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    username = None  # remove username
    email = models.EmailField(unique=True)

    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_photo = models.ImageField(upload_to='users/photos/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    is_blocked = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class OTP(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code       = models.IntegerField()
    expired_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP for {self.user.email}"

    class Meta:
        db_table = 'otp'